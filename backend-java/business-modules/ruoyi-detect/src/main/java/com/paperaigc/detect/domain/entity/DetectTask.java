package com.paperaigc.detect.domain.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 检测任务实体 —— 对齐 docs/releases/v0.1.0/sql · detect_task
 *
 * <p>Phase B 落 MyBatis-Plus。paragraphs 是子表明细，详情才拉；列表只查主表。</p>
 *
 * <p>autoResultMap=true 让 @TableField(typeHandler) 生效（JSON 列反序列化）。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName(value = "detect_task", autoResultMap = true)
public class DetectTask {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long userId;

    /** 模态：text */
    private String modality;

    private String paperTitle;
    private String status;
    private String scenario;
    private Integer threshold;
    private Double aiRate;

    private String filePath;
    private String originalFilename;
    private Long fileSize;

    private String modelVersion;

    private Integer wordCount;
    private Long bodyParagraphCount;
    private Integer excludedParagraphCount;

    /** 溯源汇总 · JSON 列 source_labels_json 反序列化到 Map */
    @TableField(value = "source_labels_json", typeHandler = JacksonTypeHandler.class)
    private Map<String, Double> sourceLabels;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
    private LocalDateTime finishedAt;

    /** 段落级明细 · 独立子表 detect_paragraph_result；不映射到主表列 */
    @TableField(exist = false)
    private List<ParagraphResult> paragraphs;
}