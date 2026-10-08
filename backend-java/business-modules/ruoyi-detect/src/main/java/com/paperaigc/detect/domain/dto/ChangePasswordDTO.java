package com.paperaigc.detect.domain.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 修改密码请求（已登录用户）
 */
@Data
public class ChangePasswordDTO {

    @NotBlank(message = "请输入原密码")
    private String oldPassword;

    @NotBlank(message = "请输入新密码")
    @Size(min = 6, max = 32, message = "新密码长度 6-32 位")
    private String newPassword;

    @NotBlank(message = "请再次输入新密码")
    private String confirmPassword;
}
