package com.paperaigc.detect.controller;

import lombok.extern.slf4j.Slf4j;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 运营大盘 · Wave 3.e (§3.1)
 *
 * <p>聚合口径：KPI 卡 · 30 天趋势 · 场景分布饼 · Top10 高活跃用户 · Top10 待处理反馈。</p>
 * <p>Phase 0 走内存 Map 聚合；生产走 Service + 预算物化 + 定时刷新。</p>
 */
@Slf4j
@RestController
@RequestMapping("/admin")
public class AdminDashboardController {

    private static final DateTimeFormatter DATE = DateTimeFormatter.ofPattern("yyyy-MM-dd");

    private final DetectController detectController;
    private final AdminUserController adminUserController;
    private final FeedbackController feedbackController;

    public AdminDashboardController(DetectController detectController,
                                    AdminUserController adminUserController,
                                    FeedbackController feedbackController) {
        this.detectController = detectController;
        this.adminUserController = adminUserController;
        this.feedbackController = feedbackController;
    }

    @GetMapping("/dashboard")
    public R<Map<String, Object>> dashboard() {
        var allTasks = detectController.getAllTasksRaw();
        var allUsers = adminUserController.getAllUsers();
        String today = LocalDate.now().toString();

        // ---------- KPI ----------
        Map<String, Object> kpi = new LinkedHashMap<>();
        kpi.put("todayNewUser",  adminUserController.countTodayNewUser());
        kpi.put("todayDetect",   (int) allTasks.stream()
                .filter(t -> String.valueOf(t.get("createdAt")).startsWith(today)).count());
        kpi.put("totalUser",     allUsers.size());
        kpi.put("totalDetect",   allTasks.size());
        kpi.put("avgAiRate", allTasks.stream()
                .filter(t -> t.get("aiRate") instanceof Number)
                .mapToDouble(t -> ((Number) t.get("aiRate")).doubleValue())
                .average().orElse(0.0));

        // ---------- 30 天趋势 ----------
        List<Map<String, Object>> trend = new ArrayList<>();
        LocalDate start = LocalDate.now().minusDays(29);
        for (int i = 0; i < 30; i++) {
            LocalDate day = start.plusDays(i);
            String key = day.format(DATE);
            long detectCount = allTasks.stream()
                    .filter(t -> String.valueOf(t.get("createdAt")).startsWith(key)).count();
            long userCount = allUsers.stream()
                    .filter(u -> String.valueOf(u.get("registeredAt")).startsWith(key)).count();
            double avgRate = allTasks.stream()
                    .filter(t -> String.valueOf(t.get("createdAt")).startsWith(key))
                    .filter(t -> t.get("aiRate") instanceof Number)
                    .mapToDouble(t -> ((Number) t.get("aiRate")).doubleValue())
                    .average().orElse(0.0);
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("date", key);
            row.put("newUser", userCount);
            row.put("detect",  detectCount);
            row.put("avgAiRate", round1(avgRate));
            trend.add(row);
        }

        // ---------- 场景分布 ----------
        Map<String, Long> scenarioCnt = new LinkedHashMap<>();
        for (String s : List.of("academic_bachelor","academic_master","academic_phd",
                                "job_report","self_media","other")) {
            scenarioCnt.put(s, 0L);
        }
        for (var t : allTasks) {
            String sc = String.valueOf(t.getOrDefault("scenario", "other"));
            scenarioCnt.merge(sc, 1L, Long::sum);
        }

        // ---------- Top 10 高活跃用户（近 7 天） ----------
        LocalDateTime weekAgo = LocalDateTime.now().minusDays(7);
        Map<Long, Long> userDetectCnt = new HashMap<>();
        for (var t : allTasks) {
            Long uid = numLong(t.get("userId"));
            if (uid == null) continue;
            String createdAt = String.valueOf(t.get("createdAt"));
            if (createdAt.compareTo(weekAgo.format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"))) < 0) continue;
            userDetectCnt.merge(uid, 1L, Long::sum);
        }
        List<Map<String, Object>> topUsers = userDetectCnt.entrySet().stream()
                .sorted(Map.Entry.<Long, Long>comparingByValue().reversed())
                .limit(10)
                .map(e -> {
                    Map<String, Object> row = new HashMap<>();
                    row.put("userId", e.getKey());
                    row.put("detectCount", e.getValue());
                    row.put("userLabel", userLabelOf(e.getKey()));
                    return row;
                })
                .toList();

        // ---------- Top 10 待处理反馈 ----------
        var feedbackList = feedbackController.list("PENDING", null, 1, 10).getData();
        Object pendingRows = feedbackList == null ? List.of() : feedbackList.get("rows");

        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("kpi", kpi);
        resp.put("trend", trend);
        resp.put("scenarioDist", scenarioCnt);
        resp.put("topUsers", topUsers);
        resp.put("pendingFeedback", pendingRows);
        return R.ok(resp);
    }

    private String userLabelOf(Long uid) {
        for (Map<String, Object> u : adminUserController.getAllUsers()) {
            if (uid.equals(u.get("id"))) return String.valueOf(u.get("identity"));
        }
        return "user#" + uid;
    }

    private static Long numLong(Object o) {
        if (o == null) return null;
        if (o instanceof Number n) return n.longValue();
        try { return Long.parseLong(String.valueOf(o)); } catch (NumberFormatException e) { return null; }
    }

    private static double round1(double v) {
        return Math.round(v * 10.0) / 10.0;
    }
}
