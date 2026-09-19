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
 * C 端用户档案（Phase B 落 user_profile 表）
 *
 * <p>跟若依 sys_user 严格分离：sys_user 是后台运营账号；user_profile 是 C 端手机/微信/邮箱
 * 注册用户。字段与运营后台 §3.2 列表 UI 对齐。类名 AdminUser 是 Phase A 早期误命名，
 * 保留避免 rename 大改；Phase C 统一 rename UserProfile 时再动。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("user_profile")
public class AdminUser {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 登录方式：phone / wechat / email */
    private String loginType;

    /** 脱敏账号：138****5678 / abc****@163.com / oGvz1w**** */
    private String identity;

    /** 累计检测数缓存（Phase B 用 CronJob 或 CDC 从 detect_task 聚合刷新） */
    private Integer detectCount;

    private LocalDateTime lastLoginAt;
    private LocalDateTime registeredAt;

    /** NORMAL / BANNED / INACTIVE / SUSPICIOUS */
    private String status;
}
