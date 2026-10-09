package com.paperaigc.detect.domain.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 登录请求
 */
@Data
public class LoginDTO {

    @NotBlank(message = "用户名不能为空")
    private String username;

    @NotBlank(message = "密码不能为空")
    private String password;

    /** 图形验证码 id（前端传了则校验） */
    private String captchaId;
    /** 图形验证码输入 */
    private String captchaCode;
}
