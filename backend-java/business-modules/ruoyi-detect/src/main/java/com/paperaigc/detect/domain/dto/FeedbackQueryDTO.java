package com.paperaigc.detect.domain.dto;

import lombok.Data;

/**
 * 反馈列表查询条件（C 端 / 运营后台共用）
 */
@Data
public class FeedbackQueryDTO {

    /** 状态过滤：PENDING / PROCESSING / REPLIED / IGNORED；空为不限 */
    private String status;

    /** 关键字：content 或 contact 大小写不敏感 contains */
    private String keyword;

    /** C 端"我的反馈"用；后台不传 */
    private Long userId;

    /** 分页 · 从 1 开始 */
    private Integer pageNum = 1;
    private Integer pageSize = 20;
}
