package com.paperaigc.detect.domain.dto;

import lombok.Data;

/**
 * 平台账号列表查询
 */
@Data
public class AdminAccountQueryDTO {
    /** 关键字：用户名 / 姓名 / 组织 contains */
    private String keyword;
    /** USER / ADMIN / OPS_ADMIN */
    private String role;
    /** 1 正常 / 0 停用 */
    private Integer status;

    private Integer pageNum = 1;
    private Integer pageSize = 20;
}
