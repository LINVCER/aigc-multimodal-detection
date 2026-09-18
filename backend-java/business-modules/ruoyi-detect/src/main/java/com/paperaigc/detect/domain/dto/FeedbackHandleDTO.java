package com.paperaigc.detect.domain.dto;

import lombok.Data;

/**
 * 运营后台处理反馈请求
 *
 * <p>路径：{@code POST /admin/feedback/{id}/handle}</p>
 * <p>status 与 reply 的联动校验（REPLIED 必带 reply）在 Service 层。</p>
 */
@Data
public class FeedbackHandleDTO {

    /** 新状态：PROCESSING / REPLIED / IGNORED；缺省视为 REPLIED */
    private String status;

    /** 回复内容；REPLIED 状态必填 */
    private String reply;

    /** 处理运营账号 ID；Sa-Token 接入后从上下文取 */
    private Long handledBy;
}
