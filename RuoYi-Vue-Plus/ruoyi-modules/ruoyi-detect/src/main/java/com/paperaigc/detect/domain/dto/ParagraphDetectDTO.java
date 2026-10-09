package com.paperaigc.detect.domain.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * §8.2 单段直接检测（非任务，粘贴文本走此接口）
 */
@Data
public class ParagraphDetectDTO {

    /** 待检测文本 */
    @NotBlank(message = "不能为空")
    private String text;

    /** 是否返回句级明细（前端高亮用） */
    private Boolean returnSentences = true;
}
