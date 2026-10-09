package com.paperaigc.detect.domain.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 图形验证码响应
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CaptchaVO {
    /** 验证码 id，提交登录/注册时回传 */
    private String captchaId;
    /** data:image/png;base64,... */
    private String imageBase64;
}
