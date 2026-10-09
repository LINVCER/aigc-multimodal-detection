package com.paperaigc.detect.domain.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 句子级检测结果 —— 对齐 docs/releases/v0.1.0/sql · detect_sentence_result
 *
 * <p>Phase B 落库。业务上按 (task_id, paragraph_idx, sentence_idx) 唯一。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("detect_sentence_result")
public class SentenceResult {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 外键 → detect_task.id */
    private Long taskId;
    /** 归属段序号 */
    private Integer paragraphIdx;

    private Integer sentenceIdx;
    private String text;
    private Double aiProb;
}
