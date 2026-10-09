package com.paperaigc.detect.domain.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Map;

/**
 * 检测数据按天 × 场景 × 状态物化统计 —— detect_statistics_daily（V0.3.0.008）
 *
 * <p>scenario / status 取 'all' 表示不分该维。avg_ai_rate 由 ai_rate_sum / done_count 得出，
 * 增量更新时两者一起写。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName(value = "detect_statistics_daily", autoResultMap = true)
public class DetectStatisticsDaily {

    public static final String ALL = "all";

    @TableId(type = IdType.AUTO)
    private Long id;

    private LocalDate statDate;
    private String scenario;
    private String status;
    private Integer totalCount;
    private Integer doneCount;
    private BigDecimal aiRateSum;
    private BigDecimal avgAiRate;
    private Integer passCount;
    private Integer overCount;

    @TableField(value = "source_labels_json", typeHandler = JacksonTypeHandler.class)
    private Map<String, Long> sourceLabels;

    private LocalDateTime updatedAt;
}
