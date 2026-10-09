package com.paperaigc.detect.domain.vo;

import com.paperaigc.detect.domain.entity.AuthUser;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 登录响应
 *
 * <p>前端 auth store 消费字段：accessToken + user.id/username/realName/role/orgName。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class LoginVO {
    private String accessToken;
    /** token 有效期（秒），闲置超时失效 */
    private Long expiresIn;
    private AuthUser user;
}
