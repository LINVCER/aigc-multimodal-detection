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

import java.util.List;

/**
 * 段落级检测结果 —— 对齐 docs/releases/v0.1.0/sql · detect_paragraph_result
 *
 * <p>Phase B 落库。表主键是自增 id，业务上按 (task_id, paragraph_idx) 唯一（UK 已建）。
 * sentences 是子表 · @TableField(exist=false)，Repository 层负责组装。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName(value = "detect_paragraph_result", autoResultMap = true)
public class ParagraphResult {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 外键 → detect_task.id */
    private Long taskId;

    private Integer paragraphIdx;
    private String text;
    private boolean excluded;
    private String excludeReason;
    private Double aiProb;
    private Double calibratedProb;

    /** JSON · [lower, upper] · Python 返回结构 */
    @TableField(value = "confidence_interval", typeHandler = JacksonTypeHandler.class)
    private Object confidenceInterval;

    private String sourceLabel;
    private String sectionName;

    /** JSON · 段落级警告 */
    @TableField(value = "warnings_json", typeHandler = JacksonTypeHandler.class)
    private List<String> warnings;

    /** 句级明细 · 独立子表 detect_sentence_result */
    @TableField(exist = false)
    private List<SentenceResult> sentences;
}
