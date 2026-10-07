package com.paperaigc.detect.domain.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 平台账号 —— auth_user（V0.3.0.009）
 *
 * <p>只存登录凭据与角色；登录态用户信息由 {@link AuthUser} 承载（不含密码）。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("auth_user")
public class UserAccount {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 登录名（学号 / 工号 / 邮箱） */
    private String username;
    /** BCrypt hash */
    private String passwordHash;
    private String realName;
    /** USER / ADMIN / OPS_ADMIN */
    private String role;
    private String orgName;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
