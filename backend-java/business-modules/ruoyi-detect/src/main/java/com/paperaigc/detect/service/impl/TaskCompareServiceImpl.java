package com.paperaigc.detect.service.impl;

import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.entity.ParagraphResult;
import com.paperaigc.detect.domain.vo.TaskCompareVO;
import com.paperaigc.detect.repository.IDetectTaskRepository;
import com.paperaigc.detect.service.ITaskCompareService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;

/**
 * 复测对比实现：段落按字符二元组 Jaccard 贪心配对，再算概率差
 */
@Service
@RequiredArgsConstructor
public class TaskCompareServiceImpl implements ITaskCompareService {

    /** 低于这个相似度不算同一段（重写幅度大的段会落到 added / removed，这是期望行为） */
    private static final double MATCH_THRESHOLD = 0.35;
    /** 概率变化小于这个数算 same */
    private static final double SAME_EPS = 0.05;

    private final IDetectTaskRepository taskRepository;

    @Override
    public TaskCompareVO compare(Long taskId) {
        DetectTask curr = taskRepository.findById(taskId)
                .orElseThrow(() -> new BizException(ErrorCode.DETECT_TASK_NOT_FOUND));
        if (curr.getParentTaskId() == null) {
            throw new BizException(ErrorCode.PARAM_INVALID, "这份报告没有关联上一次检测");
        }
        DetectTask parent = taskRepository.findById(curr.getParentTaskId())
                .orElseThrow(() -> new BizException(ErrorCode.DETECT_TASK_NOT_FOUND, "上一次的任务已不存在"));

        List<ParagraphResult> cp = body(curr.getParagraphs());
        List<ParagraphResult> pp = body(parent.getParagraphs());
        List<Set<String>> cg = cp.stream().map(p -> bigrams(p.getText())).toList();
        List<Set<String>> pg = pp.stream().map(p -> bigrams(p.getText())).toList();

        // 贪心配对：按相似度从高到低取未占用的对
        List<double[]> pairs = new ArrayList<>();   // [sim, ci, pi]
        for (int i = 0; i < cp.size(); i++) {
            for (int j = 0; j < pp.size(); j++) {
                double s = jaccard(cg.get(i), pg.get(j));
                if (s >= MATCH_THRESHOLD) pairs.add(new double[]{s, i, j});
            }
        }
        pairs.sort((a, b) -> Double.compare(b[0], a[0]));
        int[] matchOfCurr = new int[cp.size()];
        int[] matchOfParent = new int[pp.size()];
        java.util.Arrays.fill(matchOfCurr, -1);
        java.util.Arrays.fill(matchOfParent, -1);
        double[] simOfCurr = new double[cp.size()];
        for (double[] pr : pairs) {
            int i = (int) pr[1], j = (int) pr[2];
            if (matchOfCurr[i] >= 0 || matchOfParent[j] >= 0) continue;
            matchOfCurr[i] = j;
            matchOfParent[j] = i;
            simOfCurr[i] = pr[0];
        }

        List<TaskCompareVO.Row> rows = new ArrayList<>();
        int down = 0, up = 0, added = 0, removed = 0;
        for (int i = 0; i < cp.size(); i++) {
            ParagraphResult c = cp.get(i);
            Double cprob = c.getCalibratedProb();
            if (matchOfCurr[i] < 0) {
                added++;
                rows.add(TaskCompareVO.Row.builder().currIdx(c.getParagraphIdx()).preview(preview(c.getText()))
                        .currProb(cprob).status("added").build());
                continue;
            }
            ParagraphResult p = pp.get(matchOfCurr[i]);
            Double pprob = p.getCalibratedProb();
            Double delta = (cprob == null || pprob == null) ? null : round(cprob - pprob);
            String status = "same";
            if (delta != null && delta <= -SAME_EPS) { status = "down"; down++; }
            else if (delta != null && delta >= SAME_EPS) { status = "up"; up++; }
            rows.add(TaskCompareVO.Row.builder()
                    .currIdx(c.getParagraphIdx()).parentIdx(p.getParagraphIdx())
                    .preview(preview(c.getText()))
                    .currProb(cprob).parentProb(pprob).delta(delta)
                    .status(status).similarity(round(simOfCurr[i]))
                    .build());
        }
        for (int j = 0; j < pp.size(); j++) {
            if (matchOfParent[j] >= 0) continue;
            removed++;
            ParagraphResult p = pp.get(j);
            rows.add(TaskCompareVO.Row.builder().parentIdx(p.getParagraphIdx()).preview(preview(p.getText()))
                    .parentProb(p.getCalibratedProb()).status("removed").build());
        }

        boolean comparable = Objects.equals(curr.getModelVersion(), parent.getModelVersion());
        Double deltaRate = (curr.getAiRate() == null || parent.getAiRate() == null) ? null
                : round(curr.getAiRate() - parent.getAiRate());
        boolean pass = curr.getAiRate() != null && curr.getThreshold() != null && curr.getAiRate() <= curr.getThreshold();
        int changed = down + up + added + removed;
        String headline;
        if (!comparable) {
            headline = "两次检测用的模型版本不同，AI 率不可直接比较；段级变化仅供参考";
        } else if (deltaRate == null) {
            headline = "有一次检测没有 AI 率，无法比较";
        } else {
            String dir = deltaRate < 0 ? "下降 " + Math.abs(deltaRate) + "pp" : deltaRate > 0 ? "上升 " + deltaRate + "pp" : "持平";
            headline = "改动了 " + changed + " 段，整体 AI 率" + dir + (pass ? "，已低于红线" : "，仍高于红线");
        }

        return TaskCompareVO.builder()
                .current(side(curr, cp.size())).parent(side(parent, pp.size()))
                .comparable(comparable)
                .summary(TaskCompareVO.Summary.builder()
                        .deltaRate(deltaRate).pass(pass).changed(changed)
                        .down(down).up(up).added(added).removed(removed).headline(headline).build())
                .rows(rows)
                .build();
    }

    private static TaskCompareVO.Side side(DetectTask t, int body) {
        return TaskCompareVO.Side.builder()
                .id(t.getId()).paperTitle(t.getPaperTitle()).aiRate(t.getAiRate()).threshold(t.getThreshold())
                .modelVersion(t.getModelVersion())
                .createdAt(t.getCreatedAt() == null ? null : t.getCreatedAt().toString())
                .bodyParagraphs(body).build();
    }

    private static List<ParagraphResult> body(List<ParagraphResult> ps) {
        if (ps == null) return List.of();
        return ps.stream().filter(p -> !p.isExcluded() && p.getText() != null && !p.getText().isBlank()).toList();
    }

    /** 字符二元组集合，忽略空白与标点，避免排版差异影响相似度 */
    private static Set<String> bigrams(String text) {
        Set<String> out = new HashSet<>();
        if (text == null) return out;
        StringBuilder sb = new StringBuilder(text.length());
        for (char ch : text.toCharArray()) {
            if (Character.isLetterOrDigit(ch)) sb.append(Character.toLowerCase(ch));
        }
        for (int i = 0; i + 1 < sb.length(); i++) out.add(sb.substring(i, i + 2));
        return out;
    }

    private static double jaccard(Set<String> a, Set<String> b) {
        if (a.isEmpty() || b.isEmpty()) return 0;
        int inter = 0;
        for (String s : a) if (b.contains(s)) inter++;
        return (double) inter / (a.size() + b.size() - inter);
    }

    private static String preview(String s) {
        if (s == null) return "";
        return s.length() <= 60 ? s : s.substring(0, 60);
    }

    private static Double round(double v) {
        return Math.round(v * 1000) / 1000.0;
    }
}
