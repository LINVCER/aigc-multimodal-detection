package com.paperaigc.detect.service;

import com.paperaigc.detect.domain.entity.ScenarioThreshold;

import java.util.List;

/**
 * 场景阈值服务
 *
 * <p>取代 {@code ScenarioConstants.threshold/label} 硬编码调用；DB 查询走 5 分钟本地缓存。
 * DB 无对应记录时兜底 ScenarioConstants，避免历史 seed 缺失导致 detect 崩溃。</p>
 */
public interface IScenarioThresholdService {

    /**
     * 场景 → AI 率红线（%）
     * @param scenario 场景码
     * @return 阈值（1-100 整数）；未知场景兜底 ScenarioConstants.threshold
     */
    int threshold(String scenario);

    /** 场景 → 展示名；未知兜底 ScenarioConstants.label */
    String label(String scenario);

    /** 全量启用配置（运营后台 §3.7 列表用；也用于场景选择器）*/
    List<ScenarioThreshold> listAll();

    /**
     * 运营后台改阈值 · 更新 DB + 清缓存下次即时生效
     * @param scenario 场景码
     * @param threshold 新阈值
     * @param enabled 是否启用
     */
    void updateThreshold(String scenario, int threshold, boolean enabled);

    /** 手动清缓存（DB 数据被外部脚本改动时用）*/
    void invalidateCache();
}
