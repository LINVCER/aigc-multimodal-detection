package com.paperaigc.detect.repository.impl;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.entity.ParagraphResult;
import com.paperaigc.detect.domain.entity.SentenceResult;
import com.paperaigc.detect.mapper.DetectParagraphResultMapper;
import com.paperaigc.detect.mapper.DetectSentenceResultMapper;
import com.paperaigc.detect.mapper.DetectTaskMapper;
import com.paperaigc.detect.repository.IDetectTaskRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Primary;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;

/**
 * detect_task 三表 · MyBatis-Plus 实现（Phase B · Batch 3）
 *
 * <p>{@code @Primary} 顶掉 InMemory。主表 + 段/句两张子表事务由 {@code @Transactional} 覆盖。</p>
 *
 * <p>约束与取舍：</p>
 * <ul>
 *   <li>save/update 段/句用"先删旧再全量插入"策略，简单可靠但写放大；Phase 0 数据量小可接受，
 *       生产改为按 idx 差量更新</li>
 *   <li>findAll 只查主表（不加载 paragraphs / sentences），列表接口性能优先</li>
 *   <li>findById 一次拉主表 + 段全量 + 句全量，Service 层组装：句按 paragraphIdx 分组塞回段</li>
 *   <li>音频段 audioSegments 通过 detect_task.audio_segments_json 单列 JSON 存储（无独立表）</li>
 * </ul>
 */
@Primary
@Repository
@RequiredArgsConstructor
public class MybatisDetectTaskRepository implements IDetectTaskRepository {

    private final DetectTaskMapper taskMapper;
    private final DetectParagraphResultMapper paragraphMapper;
    private final DetectSentenceResultMapper sentenceMapper;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public DetectTask save(DetectTask task) {
        if (task.getCreatedAt() == null) task.setCreatedAt(LocalDateTime.now());
        taskMapper.insert(task);          // id 回填
        persistChildren(task);
        return task;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Optional<DetectTask> update(DetectTask task) {
        if (task.getId() == null) return Optional.empty();
        int n = taskMapper.updateById(task);
        if (n == 0) return Optional.empty();
        // 段/句子表用"删旧插新"策略，简单可靠
        deleteChildren(task.getId());
        persistChildren(task);
        return Optional.of(task);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean deleteById(Long id) {
        if (id == null) return false;
        deleteChildren(id);
        return taskMapper.deleteById(id) > 0;
    }

    @Override
    public Optional<DetectTask> findById(Long id) {
        if (id == null) return Optional.empty();
        DetectTask task = taskMapper.selectById(id);
        if (task == null) return Optional.empty();

        // 段落 + 句子分两次拉，内存组装（Phase 0 数据量小；生产量大时改一次 JOIN + resultMap）
        List<ParagraphResult> paragraphs = paragraphMapper.selectList(
                Wrappers.lambdaQuery(ParagraphResult.class)
                        .eq(ParagraphResult::getTaskId, id)
                        .orderByAsc(ParagraphResult::getParagraphIdx));

        if (!paragraphs.isEmpty()) {
            List<SentenceResult> sentences = sentenceMapper.selectList(
                    Wrappers.lambdaQuery(SentenceResult.class)
                            .eq(SentenceResult::getTaskId, id)
                            .orderByAsc(SentenceResult::getParagraphIdx)
                            .orderByAsc(SentenceResult::getSentenceIdx));

            Map<Integer, List<SentenceResult>> sentByPara = sentences.stream()
                    .collect(Collectors.groupingBy(SentenceResult::getParagraphIdx));

            for (ParagraphResult p : paragraphs) {
                p.setSentences(sentByPara.getOrDefault(p.getParagraphIdx(), List.of()));
            }
        }

        task.setParagraphs(paragraphs);
        return Optional.of(task);
    }

    @Override
    public Collection<DetectTask> findAll() {
        // 列表只查主表；详情才拉段/句
        return taskMapper.selectList(Wrappers.lambdaQuery(DetectTask.class)
                .orderByDesc(DetectTask::getCreatedAt));
    }

    /* ==================== helpers ==================== */

    private void persistChildren(DetectTask task) {
        if (task.getId() == null) return;
        Long taskId = task.getId();

        List<ParagraphResult> paragraphs = task.getParagraphs();
        if (paragraphs == null || paragraphs.isEmpty()) return;

        // 段稳定排序 · 保证 paragraph_idx 单调
        List<ParagraphResult> sortedParas = paragraphs.stream()
                .sorted(Comparator.comparing(
                        ParagraphResult::getParagraphIdx,
                        Comparator.nullsLast(Comparator.naturalOrder())))
                .toList();

        for (ParagraphResult p : sortedParas) {
            p.setId(null);                     // 让 MP 走自增
            p.setTaskId(taskId);
            paragraphMapper.insert(p);

            List<SentenceResult> sentences = p.getSentences();
            if (sentences == null || sentences.isEmpty()) continue;
            for (SentenceResult s : sentences) {
                s.setId(null);
                s.setTaskId(taskId);
                s.setParagraphIdx(p.getParagraphIdx());
                sentenceMapper.insert(s);
            }
        }
    }

    private void deleteChildren(Long taskId) {
        sentenceMapper.delete(Wrappers.lambdaQuery(SentenceResult.class)
                .eq(SentenceResult::getTaskId, taskId));
        paragraphMapper.delete(Wrappers.lambdaQuery(ParagraphResult.class)
                .eq(ParagraphResult::getTaskId, taskId));
    }
}
