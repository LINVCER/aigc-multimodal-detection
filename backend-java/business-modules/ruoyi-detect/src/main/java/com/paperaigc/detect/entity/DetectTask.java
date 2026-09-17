package com.paperaigc.detect.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 检测任务
 */
@Data
@TableName("detect_task")
public class DetectTask {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long paperId;

    /** PENDING | RUNNING | DONE | FAILED */
    private String status;

    /** 文档级 AI 率（0-100，长度加权） */
    private BigDecimal aiRate;

    /** 溯源标签分布 JSON：{"qwen":0.4,"gpt":0.3,...} */
    private String sourceLabelsJson;

    private Integer costCredit;

    /** 推理用的模型版本（灰度与审计） */
    private String modelVersion;

    private LocalDateTime createdAt;

    private LocalDateTime finishedAt;
}
