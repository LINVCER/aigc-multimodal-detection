package com.paperaigc.detect.domain.dto;

import lombok.Data;

/**
 * §4 降 AIGC 改写请求
 *
 * <p>三种入参形态：
 * <ul>
 *   <li>taskId + paragraphIdx：从任务里拿原段原文</li>
 *   <li>text：直接给一段文本，无 taskId</li>
 * </ul>
 * Service 层按优先级取原文。</p>
 */
@Data
public class HumanizeDTO {

    /** 任务 ID（选填） */
    private Long taskId;
    /** 段序号（选填） */
    private Integer paragraphIdx;
    /** 直接给的原文（无 taskId 时用） */
    private String text;
    /** 改写风格：academic / casual / concise（默认 academic） */
    private String style = "academic";
}
