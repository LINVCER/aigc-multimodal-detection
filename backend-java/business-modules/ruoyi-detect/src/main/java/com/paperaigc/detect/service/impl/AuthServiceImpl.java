package com.paperaigc.detect.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.paperaigc.detect.common.constant.AuthConstants;
import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import com.paperaigc.detect.common.util.ParamUtils;
import com.paperaigc.detect.domain.dto.ChangePasswordDTO;
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
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDateTime;
import java.util.Locale;
import java.util.UUID;
import java.util.regex.Pattern;

/**
 * 认证实现：账号密码走 auth_user 表（salt + SHA-256），微信 mock，token 内存仓储。
 *
 * <p>登录：验证码（可配置强制）→ 锁定检查 → 查表校验密码 → 账号状态 → 记最近登录。
 * 表里没有且是 admin/admin 时兜底自动建管理员（保留课题期开发便利）。</p>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements IAuthService {

    private static final Pattern HAS_LETTER = Pattern.compile("[A-Za-z]");
    private static final Pattern HAS_DIGIT = Pattern.compile("[0-9]");
    private static final Pattern USERNAME_OK = Pattern.compile("^[A-Za-z0-9_.@-]{2,64}$");

    private final IAuthTokenRepository tokenRepository;
    private final UserAccountMapper accountMapper;
    private final CaptchaService captchaService;
    private final LoginAttemptGuard attemptGuard;

    @Value("${platform.auth.captcha-required:true}")
    private boolean captchaRequired;

    @Value("${platform.auth.token-ttl-days:7}")
    private int tokenTtlDays;

    @Override
    public LoginVO login(LoginDTO dto) {
        if (ParamUtils.isBlank(dto.getUsername())) throw new BizException(ErrorCode.LOGIN_USERNAME_EMPTY);
        if (ParamUtils.isBlank(dto.getPassword())) throw new BizException(ErrorCode.LOGIN_PASSWORD_EMPTY);
        String username = dto.getUsername().trim();

        long locked = attemptGuard.lockedSeconds(username);
        if (locked > 0) throw new BizException(ErrorCode.LOGIN_LOCKED, lockedMessage(locked));
        verifyCaptcha(dto.getCaptchaId(), dto.getCaptchaCode());

        UserAccount account = findByUsername(username);
        if (account == null) {
            // 兜底：admin/admin 自动建管理员账号（课题期保留）
            if ("admin".equalsIgnoreCase(username) && "admin".equals(dto.getPassword())) {
                account = createAccount(username, dto.getPassword(), "运营管理员", AuthConstants.ROLE_OPS_ADMIN, "运营团队");
            } else {
                throw failed(username);
            }
        } else if (!verifyPassword(dto.getPassword(), account.getPasswordHash())) {
            throw failed(username);
        }
        if (account.getStatus() != null && account.getStatus() == 0) {
            throw new BizException(ErrorCode.ACCOUNT_DISABLED);
        }
        attemptGuard.reset(username);
        touchLastLogin(account.getId());
        return issueToken(account);
    }

    @Override
    public LoginVO register(RegisterDTO dto) {
        String username = dto.getUsername() == null ? "" : dto.getUsername().trim();
        if (ParamUtils.isBlank(username)) throw new BizException(ErrorCode.LOGIN_USERNAME_EMPTY);
        if (!USERNAME_OK.matcher(username).matches()) throw new BizException(ErrorCode.REGISTER_USERNAME_INVALID);
        if (ParamUtils.isBlank(dto.getPassword())) throw new BizException(ErrorCode.LOGIN_PASSWORD_EMPTY);
        verifyCaptcha(dto.getCaptchaId(), dto.getCaptchaCode());
        if (!dto.getPassword().equals(dto.getConfirmPassword())) {
            throw new BizException(ErrorCode.REGISTER_PASSWORD_MISMATCH);
        }
        checkPasswordPolicy(dto.getPassword(), username);
        if (findByUsername(username) != null) {
            throw new BizException(ErrorCode.REGISTER_USERNAME_EXISTS);
        }
        UserAccount account = createAccount(username, dto.getPassword(), username, AuthConstants.ROLE_USER, "知源个人版");
        touchLastLogin(account.getId());
        log.info("register ok: username={}", username);
        return issueToken(account);
    }

    @Override
    public void changePassword(String bearerToken, ChangePasswordDTO dto) {
        AuthUser current = me(bearerToken);
        if (!dto.getNewPassword().equals(dto.getConfirmPassword())) {
            throw new BizException(ErrorCode.REGISTER_PASSWORD_MISMATCH);
        }
        UserAccount account = accountMapper.selectById(current.getId());
        if (account == null) throw new BizException(ErrorCode.USER_NOT_FOUND);
        if (!verifyPassword(dto.getOldPassword(), account.getPasswordHash())) {
            throw new BizException(ErrorCode.OLD_PASSWORD_WRONG);
        }
        if (dto.getOldPassword().equals(dto.getNewPassword())) {
            throw new BizException(ErrorCode.PASSWORD_WEAK, "新密码不能与原密码相同");
        }
        checkPasswordPolicy(dto.getNewPassword(), account.getUsername());
        accountMapper.update(null, new LambdaUpdateWrapper<UserAccount>()
                .eq(UserAccount::getId, account.getId())
                .set(UserAccount::getPasswordHash, hashPassword(dto.getNewPassword())));
        // 改密后旧 token 作废，让所有端重新登录
        String token = AuthConstants.stripBearer(bearerToken);
        if (token != null) tokenRepository.remove(token);
        log.info("password changed: username={}", account.getUsername());
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

        return LoginVO.builder().accessToken(token).expiresIn(tokenTtlSeconds()).user(user).build();
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

    /** 失败计数 + 统一「用户名或密码错误」文案，剩余次数不多时提示 */
    private BizException failed(String username) {
        int left = attemptGuard.recordFailure(username);
        if (left == 0) {
            return new BizException(ErrorCode.LOGIN_LOCKED, lockedMessage(attemptGuard.lockedSeconds(username)));
        }
        if (left <= 2) {
            return new BizException(ErrorCode.LOGIN_PASSWORD_WRONG, "用户名或密码错误，还可尝试 " + left + " 次");
        }
        return new BizException(ErrorCode.LOGIN_PASSWORD_WRONG);
    }

    private static String lockedMessage(long seconds) {
        long minutes = Math.max(1, (seconds + 59) / 60);
        return "登录失败次数过多，请 " + minutes + " 分钟后再试";
    }

    /** captcha-required=true 时必须带 captchaId；带了就一次性校验 */
    private void verifyCaptcha(String captchaId, String captchaCode) {
        if (captchaId == null || captchaId.isBlank()) {
            if (captchaRequired) throw new BizException(ErrorCode.CAPTCHA_REQUIRED);
            return;
        }
        if (!captchaService.verify(captchaId, captchaCode)) {
            throw new BizException(ErrorCode.CAPTCHA_INVALID);
        }
    }

    /** 密码策略：6-32 位、同时含字母和数字、不等于用户名 */
    private void checkPasswordPolicy(String password, String username) {
        if (password.length() < 6 || password.length() > 32) {
            throw new BizException(ErrorCode.PASSWORD_WEAK, "密码长度 6-32 位");
        }
        if (!HAS_LETTER.matcher(password).find() || !HAS_DIGIT.matcher(password).find()) {
            throw new BizException(ErrorCode.PASSWORD_WEAK);
        }
        if (password.equalsIgnoreCase(username)) {
            throw new BizException(ErrorCode.PASSWORD_WEAK, "密码不能与用户名相同");
        }
    }

    /** 密码 hash：salt + SHA-256（课题期无 spring-security-crypto 依赖，够用；生产切 BCrypt） */
    private String hashPassword(String raw) {
        String salt = UUID.randomUUID().toString().replace("-", "").substring(0, 16);
        return salt + ":" + sha256(salt + raw);
    }

    private boolean verifyPassword(String raw, String stored) {
        if (raw == null || stored == null || !stored.contains(":")) return false;
        String[] parts = stored.split(":", 2);
        return parts.length == 2 && sha256(parts[0] + raw).equals(parts[1]);
    }

    private String sha256(String s) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(s.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : hash) sb.append(String.format(Locale.ROOT, "%02x", b));
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
                .status(1)
                .build();
        accountMapper.insert(a);
        return a;
    }

    private void touchLastLogin(Long id) {
        if (id == null) return;
        try {
            accountMapper.update(null, new LambdaUpdateWrapper<UserAccount>()
                    .eq(UserAccount::getId, id)
                    .set(UserAccount::getLastLoginAt, LocalDateTime.now()));
        } catch (Exception e) {
            // 旧库未跑 V0.3.0.010 时没有该列，不影响登录
            log.warn("update last_login_at skipped: {}", e.getMessage());
        }
    }

    private long tokenTtlSeconds() {
        return Math.max(1, tokenTtlDays) * 24L * 3600L;
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
        return LoginVO.builder().accessToken(token).expiresIn(tokenTtlSeconds()).user(user).build();
    }
}
