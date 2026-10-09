package com.paperaigc.detect.controller;

import cn.dev33.satoken.annotation.SaIgnore;
import com.paperaigc.detect.service.IDetectAnalyticsService;
import lombok.RequiredArgsConstructor;
import org.dromara.common.core.domain.R;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.Map;

/**
 * 运营后台 · 检测分析（detect-analytics-plan §6）
 */
@SaIgnore
@RestController
@RequestMapping("/admin/detect")
@RequiredArgsConstructor
public class AdminAnalyticsController {

    private final IDetectAnalyticsService analyticsService;

    /**
     * KPI + 趋势 + 分布（读物化表；AI 率分桶读明细）
     * @param dateFrom 起始日期，默认 29 天前
     * @param dateTo 截止日期，默认今天
     * @param scenario 场景；空 = 全部
     * @param status 状态；空 = 全部
     * @return 见 IDetectAnalyticsService.analytics
     */
    @GetMapping("/analytics")
    public R<Map<String, Object>> analytics(
            @RequestParam(value = "dateFrom", required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate dateFrom,
            @RequestParam(value = "dateTo", required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate dateTo,
            @RequestParam(value = "scenario", required = false) String scenario,
            @RequestParam(value = "status", required = false) String status) {
        LocalDate to = dateTo == null ? LocalDate.now() : dateTo;
        LocalDate from = dateFrom == null ? to.minusDays(29) : dateFrom;
        if (from.isAfter(to)) { LocalDate t = from; from = to; to = t; }
        if (from.isBefore(to.minusDays(366))) from = to.minusDays(366);
        return R.ok(analyticsService.analytics(from, to, scenario, status));
    }

    /**
     * 手动重算统计表（首次上线补历史、或怀疑计数漂移时）
     * @param days 最近 N 天；0 = 全部
     * @return 重算行数
     */
    @PostMapping("/statistics/rebuild")
    public R<Map<String, Object>> rebuild(@RequestParam(value = "days", defaultValue = "0") int days) {
        int rows = analyticsService.rebuild(days);
        return R.ok(Map.of("rows", rows, "days", days));
    }
}
