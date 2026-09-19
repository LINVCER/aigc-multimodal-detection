package com.paperaigc.detect.controller;

import cn.dev33.satoken.annotation.SaIgnore;
import com.paperaigc.detect.common.constant.FeedbackConstants;
import com.paperaigc.detect.domain.dto.FeedbackQueryDTO;
import com.paperaigc.detect.domain.entity.AdminUser;
import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.repository.IDetectTaskRepository;
import com.paperaigc.detect.service.IAdminUserService;
import com.paperaigc.detect.service.IFeedbackService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 运营大盘 · Wave 3.e (§3.1)
 *
 * <p>聚合口径：KPI 卡 · 30 天趋势 · 场景分布饼 · Top10 高活跃用户 · Top10 待处理反馈。</p>
 * <p>Phase 0 走内存 Map 聚合；Phase B 会切成 SQL group by + Redis 缓存。</p>
 */
@Slf4j
@SaIgnore
@RestController
@RequestMapping("/admin")
@RequiredArgsConstructor
public class AdminDashboardController {

    private static final DateTimeFormatter DATE = DateTimeFormatter.ofPattern("yyyy-MM-dd");

    private final IDetectTaskRepository taskRepository;
    private final IAdminUserService adminUserService;
    private final IFeedbackService feedbackService;

    @GetMapping("/dashboard")
    public R<Map<String, Object>> dashboard() {
        Collection<DetectTask> allTasks = taskRepository.findAll();
        Collection<AdminUser> allUsers = adminUserService.findAll();
        String today = LocalDate.now().toString();

        /* ---------- KPI ---------- */
        Map<String, Object> kpi = new LinkedHashMap<>();
        kpi.put("todayNewUser", adminUserService.countTodayNewUser());
        kpi.put("todayDetect",  (int) allTasks.stream()
                .filter(t -> t.getCreatedAt() != null && t.getCreatedAt().toLocalDate().toString().equals(today)).count());
        kpi.put("totalUser",    allUsers.size());
        kpi.put("totalDetect",  allTasks.size());
        kpi.put("avgAiRate",    allTasks.stream()
                .filter(t -> t.getAiRate() != null)
                .mapToDouble(DetectTask::getAiRate)
                .average().orElse(0.0));

        /* ---------- 30 天趋势 ---------- */
        List<Map<String, Object>> trend = new ArrayList<>();
        LocalDate start = LocalDate.now().minusDays(29);
        for (int i = 0; i < 30; i++) {
            LocalDate day = start.plusDays(i);
            String key = day.format(DATE);
            long detectCount = allTasks.stream()
                    .filter(t -> t.getCreatedAt() != null && t.getCreatedAt().toLocalDate().toString().equals(key)).count();
            long userCount = allUsers.stream()
                    .filter(u -> u.getRegisteredAt() != null && u.getRegisteredAt().toLocalDate().toString().equals(key)).count();
            double avgRate = allTasks.stream()
                    .filter(t -> t.getCreatedAt() != null && t.getCreatedAt().toLocalDate().toString().equals(key))
                    .filter(t -> t.getAiRate() != null)
                    .mapToDouble(DetectTask::getAiRate)
                    .average().orElse(0.0);
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("date", key);
            row.put("newUser", userCount);
            row.put("detect", detectCount);
            row.put("avgAiRate", round1(avgRate));
            trend.add(row);
        }

        /* ---------- 场景分布 ---------- */
        Map<String, Long> scenarioCnt = new LinkedHashMap<>();
        for (String s : List.of("academic_bachelor","academic_master","academic_phd",
                                "job_report","self_media","other")) {
            scenarioCnt.put(s, 0L);
        }
        for (DetectTask t : allTasks) {
            String sc = t.getScenario() == null ? "other" : t.getScenario();
            scenarioCnt.merge(sc, 1L, Long::sum);
        }

        /* ---------- Top 10 高活跃用户（近 7 天） ---------- */
        LocalDateTime weekAgo = LocalDateTime.now().minusDays(7);
        Map<Long, Long> userDetectCnt = new HashMap<>();
        for (DetectTask t : allTasks) {
            Long uid = t.getUserId();
            if (uid == null) continue;
            if (t.getCreatedAt() == null || t.getCreatedAt().isBefore(weekAgo)) continue;
            userDetectCnt.merge(uid, 1L, Long::sum);
        }
        List<Map<String, Object>> topUsers = userDetectCnt.entrySet().stream()
                .sorted(Map.Entry.<Long, Long>comparingByValue().reversed())
                .limit(10)
                .map(e -> {
                    Map<String, Object> row = new HashMap<>();
                    row.put("userId", e.getKey());
                    row.put("detectCount", e.getValue());
                    row.put("userLabel", adminUserService.userLabel(e.getKey()));
                    return row;
                })
                .toList();

        /* ---------- Top 10 待处理反馈 ---------- */
        FeedbackQueryDTO fq = new FeedbackQueryDTO();
        fq.setStatus(FeedbackConstants.STATUS_PENDING);
        fq.setPageNum(1); fq.setPageSize(10);
        Object pendingRows = feedbackService.page(fq).getRows();

        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("kpi", kpi);
        resp.put("trend", trend);
        resp.put("scenarioDist", scenarioCnt);
        resp.put("topUsers", topUsers);
        resp.put("pendingFeedback", pendingRows);
        return R.ok(resp);
    }

    private static double round1(double v) { return Math.round(v * 10.0) / 10.0; }
}
