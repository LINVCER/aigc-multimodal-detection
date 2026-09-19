package com.paperaigc.detect.repository.impl;

import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.repository.IDetectTaskRepository;
import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 检测任务 · 内存仓储
 *
 * <p>Phase 0 存储；Phase B 换 MybatisDetectTaskRepository 走 detect_task 表。</p>
 */
@Repository
public class InMemoryDetectTaskRepository implements IDetectTaskRepository {

    private final Map<Long, DetectTask> store = new ConcurrentHashMap<>();
    private final AtomicLong idGen = new AtomicLong(1003);

    /** 开发期 seed 演示数据，便于前端/后台联调；Phase B 切库后移除 */
    @PostConstruct
    void seed() {
        LocalDateTime now = LocalDateTime.now();
        put(1001L, "基于深度学习的中文文本情感分析研究", "DONE",    "academic_master",   15, 26.4, now.minusDays(3).withHour(14).withMinute(20));
        put(1002L, "乡村振兴背景下农产品电商发展路径研究", "RUNNING", "academic_bachelor", 20, null, now.minusDays(2).withHour(9).withMinute(12));
        put(1003L, "双碳目标下制造业绿色转型机制研究",     "DONE",    "academic_phd",      10, 8.1,  now.minusDays(4).withHour(18).withMinute(44));
    }

    private void put(long id, String title, String status, String scenario, int threshold,
                     Double aiRate, LocalDateTime createdAt) {
        DetectTask t = DetectTask.builder()
                .id(id)
                .userId(68751L)
                .modality("text")
                .paperTitle(title)
                .status(status)
                .scenario(scenario)
                .threshold(threshold)
                .aiRate(aiRate)
                .wordCount(8642)
                .bodyParagraphCount(18L)
                .createdAt(createdAt)
                .finishedAt(status.equals("DONE") ? createdAt.plusMinutes(3) : null)
                .build();
        store.put(t.getId(), t);
    }

    @Override
    public DetectTask save(DetectTask t) {
        if (t.getId() == null) t.setId(idGen.incrementAndGet());
        if (t.getCreatedAt() == null) t.setCreatedAt(LocalDateTime.now());
        store.put(t.getId(), t);
        return t;
    }

    @Override
    public Optional<DetectTask> update(DetectTask t) {
        if (t.getId() == null || !store.containsKey(t.getId())) return Optional.empty();
        store.put(t.getId(), t);
        return Optional.of(t);
    }

    @Override
    public boolean deleteById(Long id) {
        return id != null && store.remove(id) != null;
    }

    @Override
    public Optional<DetectTask> findById(Long id) {
        return Optional.ofNullable(id == null ? null : store.get(id));
    }

    @Override
    public Collection<DetectTask> findAll() {
        return store.values();
    }
}
