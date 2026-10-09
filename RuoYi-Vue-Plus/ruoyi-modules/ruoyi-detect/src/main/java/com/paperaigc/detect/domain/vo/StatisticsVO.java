package com.paperaigc.detect.domain.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * §3.7 C 端 Dashboard 统计（区别于运营大盘 §3.1）
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class StatisticsVO {
    private Integer today;
    private Integer thisMonth;
    private Integer total;
    private Integer done;
    /** 平均 AI 率（%）；无 DONE 任务时 null */
    private Double avgAiRate;
    /** 达标率（%）；无 DONE 任务时 null */
    private Double passRate;
    private List<DailyTrendRow> dailyTrend;

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class DailyTrendRow {
        private String date;      // yyyy-MM-dd
        private Integer count;
        private Double avgRate;   // 无数据时 null
    }
}
