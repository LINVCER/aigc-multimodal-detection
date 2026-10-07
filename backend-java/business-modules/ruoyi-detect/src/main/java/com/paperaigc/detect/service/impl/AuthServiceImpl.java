package com.paperaigc.detect.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.paperaigc.detect.common.constant.AuthConstants;
import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import com.paperaigc.detect.common.util.ParamUtils;
import com.paperaigc.detect.domain.dto.LoginDTO;
import com.paperaigc.detect.domain.dto.RegisterDTO;
import com.paperaigc.detect.domain.entity.AuthUser;
import com.paperaigc.detect.domain.entity.UserAccount;
import com.paperaigc.detect.domain.vo.LoginVO;
import com.paperaigc.detect.mapper.UserAccountMapper;
import com.paperaigc.detect.repository.IAuthTokenRepository;
import com.paperaigc.detect.service.IAuthService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.UUID;

/**
 * 认证实现：账号密码走 auth_user 表（BCrypt），微信 mock，token 内存仓储。
 *
 * <p>登录：查表校验密码；表里没有且是 admin/admin 时兜底自动建管理员（保留课题期开发便利）。</p>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements IAuthService {

    private final IAuthTokenRepository tokenRepository;
    private final UserAccountMapper accountMapper;
    private final CaptchaService captchaService;

    @Override
    public LoginVO login(LoginDTO dto) {
        if (ParamUtils.isBlank(dto.getUsername())) throw new BizException(ErrorCode.LOGIN_USERNAME_EMPTY);
        if (ParamUtils.isBlank(dto.getPassword())) throw new BizException(ErrorCode.LOGIN_PASSWORD_EMPTY);
        verifyCaptcha(dto.getCaptchaId(), dto.getCaptchaCode());

        String username = dto.getUsername().trim();
        UserAccount account = findByUsername(username);
        if (account == null) {
            // 兜底：admin/admin 自动建管理员账号（课题期保留）
            if ("admin".equalsIgnoreCase(username) && "admin".equals(dto.getPassword())) {
                account = createAccount(username, dto.getPassword(), "运营管理员", AuthConstants.ROLE_OPS_ADMIN, "运营团队");
            } else {
                throw new BizException(ErrorCode.LOGIN_PASSWORD_WRONG);
            }
        } else if (!verifyPassword(dto.getPassword(), account.getPasswordHash())) {
            throw new BizException(ErrorCode.LOGIN_PASSWORD_WRONG);
        }
        return issueToken(account);
    }

    @Override
    public LoginVO register(RegisterDTO dto) {
        String username = dto.getUsername() == null ? "" : dto.getUsername().trim();
        if (ParamUtils.isBlank(username)) throw new BizException(ErrorCode.LOGIN_USERNAME_EMPTY);
        if (ParamUtils.isBlank(dto.getPassword())) throw new BizException(ErrorCode.LOGIN_PASSWORD_EMPTY);
        verifyCaptcha(dto.getCaptchaId(), dto.getCaptchaCode());
        if (!dto.getPassword().equals(dto.getConfirmPassword())) {
            throw new BizException(ErrorCode.REGISTER_PASSWORD_MISMATCH);
        }
        if (findByUsername(username) != null) {
            throw new BizException(ErrorCode.REGISTER_USERNAME_EXISTS);
        }
        UserAccount account = createAccount(username, dto.getPassword(), username, AuthConstants.ROLE_USER, "知源个人版");
        log.info("register ok: username={}", username);
        return issueToken(account);
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

    /* ==================== helpers ==================== */

    /** 前端传了 captchaId 就校验（一次性）；不传则跳过（课题期兼容） */
    private void verifyCaptcha(String captchaId, String captchaCode) {
        if (captchaId != null && !captchaId.isBlank()) {
            if (!captchaService.verify(captchaId, captchaCode)) {
                throw new BizException(ErrorCode.CAPTCHA_INVALID);
            }
        }
    }

    /** 密码 hash：salt + SHA-256（课题期无 spring-security-crypto 依赖，够用；生产切 BCrypt） */
    private String hashPassword(String raw) {
        String salt = UUID.randomUUID().toString().replace("-", "").substring(0, 16);
        return salt + ":" + sha256(salt + raw);
    }

    private boolean verifyPassword(String raw, String stored) {
        if (stored == null || !stored.contains(":")) return false;
        String[] parts = stored.split(":", 2);
        return parts.length == 2 && sha256(parts[0] + raw).equals(parts[1]);
    }

    private String sha256(String s) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(s.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : hash) sb.append(String.format("%02x", b));
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 不可用", e);
        }
    }

    private UserAccount findByUsername(String username) {
        return accountMapper.selectOne(new LambdaQueryWrapper<UserAccount>().eq(UserAccount::getUsername, username));
    }

    private UserAccount createAccount(String username, String rawPassword, String realName, String role, String orgName) {
        UserAccount a = UserAccount.builder()
                .username(username)
                .passwordHash(hashPassword(rawPassword))
                .realName(realName)
                .role(role)
                .orgName(orgName)
                .build();
        accountMapper.insert(a);
        return a;
    }

    private LoginVO issueToken(UserAccount account) {
        AuthUser user = AuthUser.builder()
                .id(account.getId())
                .username(account.getUsername())
                .realName(account.getRealName() != null && !account.getRealName().isBlank() ? account.getRealName() : account.getUsername())
                .role(account.getRole() != null ? account.getRole() : AuthConstants.ROLE_USER)
                .orgName(account.getOrgName())
                .build();
        String token = UUID.randomUUID().toString().replace("-", "");
        tokenRepository.put(token, user);
        log.info("login ok: username={} role={} tokenPrefix={}", account.getUsername(), user.getRole(), token.substring(0, 8));
        return LoginVO.builder().accessToken(token).user(user).build();
    }
}
