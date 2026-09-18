package com.paperaigc.detect.service.impl;

import com.paperaigc.detect.common.constant.AuthConstants;
import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import com.paperaigc.detect.common.util.ParamUtils;
import com.paperaigc.detect.domain.dto.LoginDTO;
import com.paperaigc.detect.domain.entity.AuthUser;
import com.paperaigc.detect.domain.vo.LoginVO;
import com.paperaigc.detect.repository.IAuthTokenRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.UUID;

/**
 * 认证 mock 实现
 *
 * <p>规则：</p>
 * <ul>
 *   <li>用户名 / 密码非空即通过</li>
 *   <li>admin/admin 派 OPS_ADMIN 角色（可进 /admin/*）</li>
 *   <li>其它派 USER 角色</li>
 * </ul>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements IAuthService {

    private final IAuthTokenRepository tokenRepository;

    @Override
    public LoginVO login(LoginDTO dto) {
        if (ParamUtils.isBlank(dto.getUsername())) throw new BizException(ErrorCode.LOGIN_USERNAME_EMPTY);
        if (ParamUtils.isBlank(dto.getPassword())) throw new BizException(ErrorCode.LOGIN_PASSWORD_EMPTY);

        String username = dto.getUsername();
        boolean isAdmin = "admin".equalsIgnoreCase(username);
        AuthUser user = AuthUser.builder()
                .id((long) (Math.abs(username.hashCode()) % 100_000))
                .username(username)
                .realName(username)
                .role(isAdmin ? AuthConstants.ROLE_OPS_ADMIN : AuthConstants.ROLE_USER)
                .orgName(isAdmin ? "运营团队" : "AI 检测个人版")
                .build();

        String token = UUID.randomUUID().toString().replace("-", "");
        tokenRepository.put(token, user);
        log.info("mock login ok: username={} role={} tokenPrefix={}", username, user.getRole(), token.substring(0, 8));

        return LoginVO.builder().accessToken(token).user(user).build();
    }

    @Override
    public void logout(String bearerToken) {
        String token = AuthConstants.stripBearer(bearerToken);
        if (token != null) tokenRepository.remove(token);
    }

    @Override
    public AuthUser me(String bearerToken) {
        String token = AuthConstants.stripBearer(bearerToken);
        return tokenRepository.get(token)
                .orElseThrow(() -> new BizException(ErrorCode.LOGIN_TOKEN_INVALID));
    }
}
