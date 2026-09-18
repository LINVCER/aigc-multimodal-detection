package com.paperaigc.detect.domain.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 登录用户实体（开发期 mock）
 *
 * <p>Sa-Token 基座接入后由 sys_user 承接，本实体可删除。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AuthUser {
    private Long id;
    private String username;
    private String realName;
    /** OPS_ADMIN / USER / ADMIN，对齐 {@link com.paperaigc.detect.common.constant.AuthConstants} */
    private String role;
    private String orgName;
}
