package com.paperaigc.detect.service.impl;

import com.paperaigc.detect.common.constant.AuthConstants;
import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import com.paperaigc.detect.common.util.ParamUtils;
import com.paperaigc.detect.domain.dto.LoginDTO;
import com.paperaigc.detect.domain.entity.AuthUser;
import com.paperaigc.detect.domain.vo.LoginVO;
import com.paperaigc.detect.repository.IAuthTokenRepository;
import com.paperaigc.detect.service.IAuthService;
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
    public LoginVO loginByWechat(String code, String nickname, String avatarUrl) {
        if (ParamUtils.isBlank(code)) throw new BizException(ErrorCode.LOGIN_USERNAME_EMPTY, "缺少 wx.login code");
        // mock 假 openid（生产走 code2session 换真实 openid + session_key）
        String openid = "wx_mock_" + Integer.toHexString(code.hashCode()).substring(0, Math.min(6, code.length()));
        String uname = (nickname == null || nickname.isBlank()) ? openid : nickname;

        AuthUser user = AuthUser.builder()
                .id((long) (Math.abs(openid.hashCode()) % 100_000))
                .username(uname)
                .realName(uname)
                .role(AuthConstants.ROLE_USER)
                .orgName("微信用户")
                .build();

        String token = UUID.randomUUID().toString().replace("-", "");
        tokenRepository.put(token, user);
        log.info("mock wechat login ok: openid={} nickname={} tokenPrefix={}", openid, nickname, token.substring(0, 8));

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
