package com.paperaigc.detect.domain.dto;

import lombok.Data;

/**
 * 运营后台用户列表查询条件（§3.2）
 */
@Data
public class AdminUserQueryDTO {
    /** 登录方式：phone / wechat / email */
    private String loginType;
    /** 状态：NORMAL / BANNED / INACTIVE / SUSPICIOUS */
    private String status;
    /** 关键字：identity 或 id contains */
    private String keyword;
    /** 累计检测数区间 */
    private Integer minDetect;
    private Integer maxDetect;

    private Integer pageNum = 1;
    private Integer pageSize = 20;
}
