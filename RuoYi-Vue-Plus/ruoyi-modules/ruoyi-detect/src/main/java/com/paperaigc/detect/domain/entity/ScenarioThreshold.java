package com.paperaigc.detect.domain.entity;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 场景阈值配置 —— 对齐 docs/releases/v0.1.0/sql · detect_scenario_threshold
 *
 * <p>Phase B · Batch 4 落 DB · Caffeine 5min 缓存。运营后台改后清缓存即时生效。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("detect_scenario_threshold")
public class ScenarioThreshold {

    /** 场景码：academic_bachelor / academic_master / … · PK */
    @TableId
    private String scenario;

    /** 展示名 */
    private String label;

    /** AI 率红线（%） · DECIMAL(5,2) */
    private BigDecimal threshold;

    /** 是否启用 · 0/1 */
    private Integer enabled;

    private LocalDateTime updatedAt;
}
