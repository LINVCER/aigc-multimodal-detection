package com.paperaigc.detect.domain.vo;

import com.paperaigc.detect.domain.entity.UserAccount;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 后台账号行（不含密码）
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AdminAccountVO {
    private Long id;
    private String username;
    private String realName;
    private String role;
    private String orgName;
    /** 1 正常 / 0 停用 */
    private Integer status;
    private LocalDateTime lastLoginAt;
    private LocalDateTime createdAt;
    /** 累计检测任务数（detect_task.user_id 聚合） */
    private Integer detectCount;
    private LocalDateTime lastDetectAt;

    public static AdminAccountVO from(UserAccount a) {
        return AdminAccountVO.builder()
                .id(a.getId())
                .username(a.getUsername())
                .realName(a.getRealName())
                .role(a.getRole())
                .orgName(a.getOrgName())
                .status(a.getStatus() == null ? 1 : a.getStatus())
                .lastLoginAt(a.getLastLoginAt())
                .createdAt(a.getCreatedAt())
                .build();
    }
}
