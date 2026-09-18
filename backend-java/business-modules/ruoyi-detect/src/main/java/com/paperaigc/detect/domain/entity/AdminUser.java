package com.paperaigc.detect.domain.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 运营后台 · 用户视图实体
 *
 * <p>Phase 0：内存 seed。Sa-Token / sys_user 接入后由 sys_user + 扩展表承接。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AdminUser {
    private Long id;
    /** 登录方式：phone / wechat / email */
    private String loginType;
    /** 脱敏账号：138****5678 / abc****@163.com / oGvz1w**** */
    private String identity;
    /** 累计检测数（Phase 0 从任务列表聚合；Phase B 落 sys_user 扩展列或用视图） */
    private Integer detectCount;
    private LocalDateTime lastLoginAt;
    private LocalDateTime registeredAt;
    /** NORMAL / BANNED / INACTIVE / SUSPICIOUS */
    private String status;
}
