package com.paperaigc.detect.domain.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * C 端提交反馈请求
 *
 * <p>路径：{@code POST /api/v1/feedback}</p>
 * <p>业务校验（appeal 必带 taskId · content 长度）在 Service 层再做，
 * 此处只做通用格式校验。</p>
 */
@Data
public class FeedbackSubmitDTO {

    /** 分类：bug / suggestion / appeal */
    @NotBlank(message = "不能为空")
    private String category;

    /** 反馈内容 */
    @NotBlank(message = "不能为空")
    @Size(max = 2000, message = "长度不能超过 2000 字")
    private String content;

    /** 结果申诉关联的检测任务 ID；appeal 场景 Service 层校验必填 */
    private Long taskId;

    /** 联系方式（选填） */
    @Size(max = 128, message = "长度不能超过 128 字")
    private String contact;

    /** W3.c 登录接入前从请求体透传；接入后 Service 从 Sa-Token 取，忽略此字段 */
    private Long userId;
}
