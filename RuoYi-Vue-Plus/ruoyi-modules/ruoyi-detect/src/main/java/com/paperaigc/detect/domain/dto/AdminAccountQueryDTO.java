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
    /** 排序字段白名单：lastLoginAt / createdAt / username；缺省按 id 倒序 */
    private String sortBy;
    /** asc / desc */
    private String sortOrder;

    private Integer pageNum = 1;
    private Integer pageSize = 20;
}
