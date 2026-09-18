package com.paperaigc.detect.domain.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 检测任务实体 —— 对齐 patch-schema.sql · detect_task
 *
 * <p>Phase 0 走内存 map；Phase B 接入 MyBatis-Plus 时补 @TableName/@TableField 注解。
 * paragraphs / sourceLabels 是详情视图专用，列表视图不携带。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DetectTask {

    /** 任务 ID */
    private Long id;
    /** 提交者 ID；Sa-Token 接入后从上下文取 */
    private Long userId;

    /** 论文标题（缺省用文件名） */
    private String paperTitle;
    /** 状态：PENDING / RUNNING / DONE / FAILED */
    private String status;

    /** 使用场景：academic_bachelor / academic_master / … */
    private String scenario;
    /** 场景对应 AI 率红线（%）；快照存入，避免运营改配置后历史任务变红线 */
    private Integer threshold;

    /** 整体 AI 率（%）；DONE 后填充 */
    private Double aiRate;

    /** 原始文件存储路径；由 IStorageService 生成，本地 FS 或 MinIO key 均可 */
    private String filePath;
    /** 原始文件名（含后缀） */
    private String originalFilename;
    /** 文件大小（byte） */
    private Long fileSize;

    /** 模型版本快照，供审计与灰度对齐 */
    private String modelVersion;

    /** 字符总数（正文 + 排除） */
    private Integer wordCount;
    /** 参与 AI 率计算的正文段数 */
    private Long bodyParagraphCount;
    /** 被排除的段数 */
    private Integer excludedParagraphCount;

    private LocalDateTime createdAt;
    private LocalDateTime finishedAt;

    /** 段落级明细（列表接口不携带，详情才附） */
    private List<ParagraphResult> paragraphs;
    /** 溯源汇总 sourceLabel -> 比例 */
    private Map<String, Double> sourceLabels;
}
