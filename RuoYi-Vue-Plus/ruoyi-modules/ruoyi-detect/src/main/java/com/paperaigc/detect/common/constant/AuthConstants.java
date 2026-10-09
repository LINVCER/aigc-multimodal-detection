package com.paperaigc.detect.common.constant;

/**
 * 认证 / 角色常量（对齐前端 auth store 的 role 字段与 router.beforeEach.requiresOpsAdmin 校验）
 *
 * <p>Sa-Token 接入后 role 走若依 sys_role，本常量作为 Phase 0 的兜底以及编码期字面量避重。</p>
 */
public final class AuthConstants {

    private AuthConstants() {}

    /* ---------- Role ---------- */
    public static final String ROLE_OPS_ADMIN = "OPS_ADMIN";
    public static final String ROLE_USER      = "USER";
    public static final String ROLE_ADMIN     = "ADMIN";   // 保留：若依基座超管

    /* ---------- Token Header ---------- */
    public static final String HEADER_AUTHORIZATION = "Authorization";
    public static final String BEARER_PREFIX        = "Bearer ";

    /**
     * 剥掉 "Bearer " 前缀取纯 token；已经是纯 token 也 pass-through
     * @param header 原始 Authorization header 值
     * @return 纯 token，无 header 返回 null
     */
    public static String stripBearer(String header) {
        if (header == null || header.isBlank()) return null;
        return header.startsWith(BEARER_PREFIX) ? header.substring(BEARER_PREFIX.length()) : header;
    }
}
