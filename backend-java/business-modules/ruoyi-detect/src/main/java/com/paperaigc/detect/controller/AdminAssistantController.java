package com.paperaigc.detect.controller;

import cn.dev33.satoken.annotation.SaIgnore;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.paperaigc.detect.domain.entity.AssistantLog;
import com.paperaigc.detect.mapper.AssistantLogMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * 运营后台 · 助手运营（增长闭环 P0）
 *
 * <p>只读。知识缺口按 docs/design/202610-assistant-growth-loop-plan.md §1.1 三条件取：
 * 该走知识库的意图 + top-1 分数低于阈值（或未检索到）。界面归 product-feature-plan §3.1，这里先给数据。</p>
 */
@Slf4j
@SaIgnore
@RestController
@RequestMapping("/admin/assistant")
@RequiredArgsConstructor
public class AdminAssistantController {

    /** 该走知识库的意图；explain 走工具、chitchat / history 不需要知识 */
    private static final List<String> KB_INTENTS = List.of("policy", "guide", "other");

    private final AssistantLogMapper logMapper;

    /**
     * 知识缺口候选列表
     * @param days 最近 N 天
     * @param threshold BM25 top-1 分数阈值（方案建议先 1.0，跑两周看分布再定）
     * @param limit 条数上限
     * @return 原问题 / 意图 / 命中分 / 命中块 / 时间
     */
    @GetMapping("/knowledge-gaps")
    public R<List<Map<String, Object>>> knowledgeGaps(
            @RequestParam(value = "days", defaultValue = "14") int days,
            @RequestParam(value = "threshold", defaultValue = "1.0") BigDecimal threshold,
            @RequestParam(value = "limit", defaultValue = "100") int limit) {
        LambdaQueryWrapper<AssistantLog> qw = new LambdaQueryWrapper<AssistantLog>()
                .ge(AssistantLog::getCreatedAt, LocalDateTime.now().minusDays(Math.max(days, 1)))
                .in(AssistantLog::getIntent, KB_INTENTS)
                .isNull(AssistantLog::getErrorCode)
                .and(w -> w.isNull(AssistantLog::getKbTopScore).or().lt(AssistantLog::getKbTopScore, threshold))
                .orderByDesc(AssistantLog::getCreatedAt)
                .last("LIMIT " + Math.min(Math.max(limit, 1), 500));
        List<Map<String, Object>> rows = logMapper.selectList(qw).stream().map(l -> {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("id", l.getId());
            m.put("question", l.getQuestion());
            m.put("intent", l.getIntent());
            m.put("kbTopScore", l.getKbTopScore());
            m.put("kbTopRef", l.getKbTopRef());
            m.put("conversationId", l.getConversationId());
            m.put("createdAt", l.getCreatedAt());
            return m;
        }).toList();
        return R.ok(rows);
    }

    /**
     * 助手运营指标（方案 §7 指标总表里能直接从 assistant_log 算的部分）
     * @param days 最近 N 天
     * @param threshold 知识命中阈值
     * @return 对话数 / 用户数 / 意图分布 / 越界率 / 知识命中率 / 工具失败率 / token 用量
     */
    @GetMapping("/stats")
    public R<Map<String, Object>> stats(
            @RequestParam(value = "days", defaultValue = "7") int days,
            @RequestParam(value = "threshold", defaultValue = "1.0") BigDecimal threshold) {
        List<AssistantLog> logs = logMapper.selectList(new LambdaQueryWrapper<AssistantLog>()
                .ge(AssistantLog::getCreatedAt, LocalDateTime.now().minusDays(Math.max(days, 1))));

        long total = logs.size();
        long users = logs.stream().map(AssistantLog::getUserId).filter(u -> u != null).distinct().count();
        long boundary = logs.stream().filter(l -> Boolean.TRUE.equals(l.getBoundaryFlag())).count();
        long toolFailed = logs.stream().filter(l -> "TOOL_FAILED".equals(l.getErrorCode())).count();
        long errors = logs.stream().filter(l -> l.getErrorCode() != null).count();
        long promptTokens = logs.stream().mapToLong(l -> l.getPromptTokens() == null ? 0 : l.getPromptTokens()).sum();
        long completionTokens = logs.stream().mapToLong(l -> l.getCompletionTokens() == null ? 0 : l.getCompletionTokens()).sum();

        Map<String, Long> intents = new TreeMap<>();
        Map<String, Long> boundaryTypes = new TreeMap<>();
        long kbDenominator = 0, kbHit = 0;
        for (AssistantLog l : logs) {
            intents.merge(l.getIntent() == null ? "unknown" : l.getIntent(), 1L, Long::sum);
            if (l.getBoundaryType() != null) boundaryTypes.merge(l.getBoundaryType(), 1L, Long::sum);
            if (l.getIntent() != null && KB_INTENTS.contains(l.getIntent()) && l.getErrorCode() == null) {
                kbDenominator++;
                if (l.getKbTopScore() != null && l.getKbTopScore().compareTo(threshold) >= 0) kbHit++;
            }
        }

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("days", days);
        out.put("conversations", total);
        out.put("users", users);
        out.put("intents", intents);
        out.put("boundaryRate", rate(boundary, total));
        out.put("boundaryTypes", boundaryTypes);
        out.put("kbHitRate", rate(kbHit, kbDenominator));
        out.put("kbSample", kbDenominator);
        out.put("toolFailedRate", rate(toolFailed, total));
        out.put("errorRate", rate(errors, total));
        out.put("promptTokens", promptTokens);
        out.put("completionTokens", completionTokens);
        return R.ok(out);
    }

    private static Double rate(long num, long den) {
        return den == 0 ? null : Math.round(num * 10000.0 / den) / 10000.0;
    }
}
