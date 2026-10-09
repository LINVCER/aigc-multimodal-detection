package com.paperaigc.detect.domain.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 误判候选样本 —— detect_hard_sample（V0.3.0.006）
 *
 * <p>来源：申诉勾选段落 / 助手 create_appeal / 运营手动。运营复核 ops_verdict 后由
 * /admin/hard-samples/export 导出 JSONL，经 ml/datasets/text/build_appeal_evalset.py 进评测集。
 * <b>只进评测、不进训练</b>（docs/design/202610-assistant-growth-loop-plan.md §2.1）。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("detect_hard_sample")
public class HardSample {

    public static final String VERDICT_CONFIRM_FP = "confirm_fp";
    public static final String VERDICT_CONFIRM_TP = "confirm_tp";
    public static final String VERDICT_UNSURE = "unsure";

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long feedbackId;
    private Long taskId;
    private Integer paragraphIdx;
    /** 段落文本哈希；未授权时只有这个 */
    private String textSha256;
    /** 仅用户授权时快照 */
    private String text;
    /** 当时的 calibratedProb */
    private BigDecimal modelProb;
    private String modelVersion;
    /** 用户主张：human / ai / mixed */
    private String userLabel;
    /** 运营复核：confirm_fp / confirm_tp / unsure */
    private String opsVerdict;
    /** appeal / assistant / ops */
    private String source;
    private String scenario;
    private Long reviewedBy;
    private LocalDateTime reviewedAt;
    private LocalDateTime createdAt;
}
