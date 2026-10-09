package com.paperaigc.detect.service;

import com.paperaigc.detect.domain.entity.DetectTask;

import java.time.LocalDate;
import java.util.Map;

/**
 * 检测数据分析层（detect-analytics-plan）：物化统计表的写入与读取
 */
public interface IDetectAnalyticsService {

    /**
     * 任务到达终态（DONE / FAILED）时增量计入当天分片；调用方保证只调一次
     * @param task 终态任务
     */
    void record(DetectTask task);

    /**
     * 任务重试 / 删除前把之前计入的分片扣回（只对 DONE / FAILED 有效，计数不低于 0）
     * @param task 扣回前的任务状态
     */
    void revert(DetectTask task);

    /**
     * 从 detect_task 全量重算最近 N 天的统计行（REPLACE 语义）
     * @param days 最近 N 天；<= 0 表示全部
     * @return 重算的行数
     */
    int rebuild(int days);

    /**
     * 后台「检测分析」页数据
     * @param from 起始日期（含）
     * @param to 截止日期（含）
     * @param scenario 场景；空 = 全部
     * @param status 状态；空 = 全部
     * @return kpi / trend / scenarioDist / statusDist / rateBuckets / sourceDist
     */
    Map<String, Object> analytics(LocalDate from, LocalDate to, String scenario, String status);
}
