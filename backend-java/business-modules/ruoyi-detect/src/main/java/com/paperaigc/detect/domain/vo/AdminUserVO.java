package com.paperaigc.detect.domain.vo;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.paperaigc.detect.domain.entity.AdminUser;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 后台用户列表响应
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AdminUserVO {
    private Long id;
    private String loginType;
    private String identity;
    private Integer detectCount;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime lastLoginAt;
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime registeredAt;

    private String status;

    public static AdminUserVO from(AdminUser u) {
        if (u == null) return null;
        return AdminUserVO.builder()
                .id(u.getId())
                .loginType(u.getLoginType())
                .identity(u.getIdentity())
                .detectCount(u.getDetectCount())
                .lastLoginAt(u.getLastLoginAt())
                .registeredAt(u.getRegisteredAt())
                .status(u.getStatus())
                .build();
    }
}
