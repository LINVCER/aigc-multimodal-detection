package com.paperaigc.detect.service.impl;

import com.paperaigc.detect.common.constant.AuthConstants;
import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import com.paperaigc.detect.common.util.PasswordHasher;
import com.paperaigc.detect.domain.dto.ChangePasswordDTO;
import com.paperaigc.detect.domain.dto.LoginDTO;
import com.paperaigc.detect.domain.dto.RegisterDTO;
import com.paperaigc.detect.domain.entity.AuthUser;
import com.paperaigc.detect.domain.entity.UserAccount;
import com.paperaigc.detect.domain.vo.LoginVO;
import com.paperaigc.detect.mapper.UserAccountMapper;
import com.paperaigc.detect.repository.IAuthTokenRepository;
import com.paperaigc.detect.support.MybatisTestSupport;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 认证服务单元测试 —— 登录 / 注册 / 改密 校验分支
 */
@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
@DisplayName("AuthServiceImpl · 认证服务")
class AuthServiceImplTest {

    @Mock private IAuthTokenRepository tokenRepository;
    @Mock private UserAccountMapper accountMapper;
    @Mock private CaptchaService captchaService;
    @Mock private LoginAttemptGuard attemptGuard;

    private AuthServiceImpl service;

    @BeforeAll
    static void initMp() {
        MybatisTestSupport.init(UserAccount.class);
    }

    @BeforeEach
    void setUp() {
        service = new AuthServiceImpl(tokenRepository, accountMapper, captchaService, attemptGuard);
        ReflectionTestUtils.setField(service, "captchaRequired", false);
        ReflectionTestUtils.setField(service, "tokenTtlDays", 7);
    }

    /* ==================== 登录 ==================== */

    @Test
    @DisplayName("用户名为空 → LOGIN_USERNAME_EMPTY")
    void loginUsernameBlank() {
        LoginDTO dto = loginDto("  ", "pwd123");
        assertThatThrownBy(() -> service.login(dto))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode())
                .isEqualTo(ErrorCode.LOGIN_USERNAME_EMPTY.getCode());
    }

    @Test
    @DisplayName("密码为空 → LOGIN_PASSWORD_EMPTY")
    void loginPasswordBlank() {
        assertThatThrownBy(() -> service.login(loginDto("bob", "")))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode())
                .isEqualTo(ErrorCode.LOGIN_PASSWORD_EMPTY.getCode());
    }

    @Test
    @DisplayName("账号不存在且非 admin/admin → 记录失败次数并报错")
    void loginUnknownUser() {
        when(accountMapper.selectOne(any())).thenReturn(null);
        when(attemptGuard.recordFailure("nobody")).thenReturn(3);

        assertThatThrownBy(() -> service.login(loginDto("nobody", "pwd123")))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode())
                .isEqualTo(ErrorCode.LOGIN_PASSWORD_WRONG.getCode());
        verify(attemptGuard).recordFailure("nobody");
    }

    @Test
    @DisplayName("admin/admin 且表内无账号 → 自动建管理员并签发 token")
    void loginAdminBootstrap() {
        when(accountMapper.selectOne(any())).thenReturn(null);
        when(accountMapper.insert(any(UserAccount.class))).thenReturn(1);

        LoginVO vo = service.login(loginDto("admin", "admin"));

        assertThat(vo.getAccessToken()).hasSize(32);
        assertThat(vo.getUser().getRole()).isEqualTo(AuthConstants.ROLE_OPS_ADMIN);
        verify(accountMapper).insert(any(UserAccount.class));
        verify(tokenRepository).put(anyString(), any(AuthUser.class));
    }

    @Test
    @DisplayName("密码错误 → 记录失败次数")
    void loginWrongPassword() {
        UserAccount acc = account(1L, "bob", "right123", 1);
        when(accountMapper.selectOne(any())).thenReturn(acc);
        when(attemptGuard.recordFailure("bob")).thenReturn(4);

        assertThatThrownBy(() -> service.login(loginDto("bob", "wrong123")))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode())
                .isEqualTo(ErrorCode.LOGIN_PASSWORD_WRONG.getCode());
        verify(attemptGuard).recordFailure("bob");
    }

    @Test
    @DisplayName("账号已停用 → ACCOUNT_DISABLED")
    void loginDisabled() {
        UserAccount acc = account(1L, "bob", "right123", 0);
        when(accountMapper.selectOne(any())).thenReturn(acc);

        assertThatThrownBy(() -> service.login(loginDto("bob", "right123")))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode())
                .isEqualTo(ErrorCode.ACCOUNT_DISABLED.getCode());
    }

    @Test
    @DisplayName("登录成功 → 清零失败计数并签发 token，有效期 7 天")
    void loginSuccess() {
        UserAccount acc = account(9L, "bob", "right123", 1);
        when(accountMapper.selectOne(any())).thenReturn(acc);

        LoginVO vo = service.login(loginDto("bob", "right123"));

        assertThat(vo.getAccessToken()).hasSize(32);
        assertThat(vo.getExpiresIn()).isEqualTo(7L * 24 * 3600);
        assertThat(vo.getUser().getId()).isEqualTo(9L);
        assertThat(vo.getUser().getUsername()).isEqualTo("bob");
        verify(attemptGuard).reset("bob");
        verify(tokenRepository).put(anyString(), any(AuthUser.class));
    }

    /* ==================== 注册 ==================== */

    @Test
    @DisplayName("用户名含非法字符 → REGISTER_USERNAME_INVALID")
    void registerInvalidUsername() {
        RegisterDTO dto = registerDto("bad name!", "abc123", "abc123");
        assertThatThrownBy(() -> service.register(dto))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode())
                .isEqualTo(ErrorCode.REGISTER_USERNAME_INVALID.getCode());
    }

    @Test
    @DisplayName("开启验证码但未传 → CAPTCHA_REQUIRED")
    void registerCaptchaRequired() {
        ReflectionTestUtils.setField(service, "captchaRequired", true);
        RegisterDTO dto = registerDto("newuser", "abc123", "abc123");
        assertThatThrownBy(() -> service.register(dto))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode())
                .isEqualTo(ErrorCode.CAPTCHA_REQUIRED.getCode());
    }

    @Test
    @DisplayName("两次密码不一致 → REGISTER_PASSWORD_MISMATCH")
    void registerPasswordMismatch() {
        assertThatThrownBy(() -> service.register(registerDto("newuser", "abc123", "abc124")))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode())
                .isEqualTo(ErrorCode.REGISTER_PASSWORD_MISMATCH.getCode());
    }

    @Test
    @DisplayName("弱密码（不含数字）→ PASSWORD_WEAK")
    void registerWeakPassword() {
        assertThatThrownBy(() -> service.register(registerDto("newuser", "abcdef", "abcdef")))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode())
                .isEqualTo(ErrorCode.PASSWORD_WEAK.getCode());
    }

    @Test
    @DisplayName("用户名已存在 → REGISTER_USERNAME_EXISTS")
    void registerUsernameExists() {
        when(accountMapper.selectOne(any())).thenReturn(account(1L, "newuser", "abc123", 1));
        assertThatThrownBy(() -> service.register(registerDto("newuser", "abc123", "abc123")))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode())
                .isEqualTo(ErrorCode.REGISTER_USERNAME_EXISTS.getCode());
    }

    @Test
    @DisplayName("注册成功 → 落库并签发 USER 角色 token")
    void registerSuccess() {
        when(accountMapper.selectOne(any())).thenReturn(null);
        when(accountMapper.insert(any(UserAccount.class))).thenReturn(1);

        LoginVO vo = service.register(registerDto("newuser", "abc123", "abc123"));

        assertThat(vo.getAccessToken()).hasSize(32);
        assertThat(vo.getUser().getRole()).isEqualTo(AuthConstants.ROLE_USER);
        verify(accountMapper).insert(any(UserAccount.class));
    }

    /* ==================== 其它 ==================== */

    @Test
    @DisplayName("usernameAvailable：非法格式 / 已存在 → false，可用 → true")
    void usernameAvailable() {
        assertThat(service.usernameAvailable("a")).isFalse();
        assertThat(service.usernameAvailable(null)).isFalse();

        when(accountMapper.selectOne(any())).thenReturn(null);
        assertThat(service.usernameAvailable("free_name")).isTrue();

        when(accountMapper.selectOne(any())).thenReturn(account(1L, "taken", "abc123", 1));
        assertThat(service.usernameAvailable("taken")).isFalse();
    }

    @Test
    @DisplayName("me：token 无效 → LOGIN_TOKEN_INVALID")
    void meInvalidToken() {
        when(tokenRepository.get(any())).thenReturn(Optional.empty());
        assertThatThrownBy(() -> service.me("Bearer deadbeef"))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode())
                .isEqualTo(ErrorCode.LOGIN_TOKEN_INVALID.getCode());
    }

    @Test
    @DisplayName("me：token 有效 → 返回用户")
    void meValidToken() {
        AuthUser user = AuthUser.builder().id(1L).username("bob").role(AuthConstants.ROLE_USER).build();
        when(tokenRepository.get("abc")).thenReturn(Optional.of(user));
        assertThat(service.me("Bearer abc").getUsername()).isEqualTo("bob");
    }

    @Test
    @DisplayName("改密：两次新密码不一致 → REGISTER_PASSWORD_MISMATCH")
    void changePasswordMismatch() {
        when(tokenRepository.get(any())).thenReturn(Optional.of(AuthUser.builder().id(1L).username("bob").build()));
        ChangePasswordDTO dto = new ChangePasswordDTO();
        dto.setOldPassword("old123");
        dto.setNewPassword("new123");
        dto.setConfirmPassword("new999");

        assertThatThrownBy(() -> service.changePassword("Bearer t", dto))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode())
                .isEqualTo(ErrorCode.REGISTER_PASSWORD_MISMATCH.getCode());
    }

    @Test
    @DisplayName("改密：原密码错误 → OLD_PASSWORD_WRONG")
    void changePasswordOldWrong() {
        when(tokenRepository.get(any())).thenReturn(Optional.of(AuthUser.builder().id(1L).username("bob").build()));
        when(accountMapper.selectById(1L)).thenReturn(account(1L, "bob", "old123", 1));
        ChangePasswordDTO dto = new ChangePasswordDTO();
        dto.setOldPassword("badold");
        dto.setNewPassword("new123");
        dto.setConfirmPassword("new123");

        assertThatThrownBy(() -> service.changePassword("Bearer t", dto))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode())
                .isEqualTo(ErrorCode.OLD_PASSWORD_WRONG.getCode());
    }

    /* ==================== fixtures ==================== */

    private static LoginDTO loginDto(String u, String p) {
        LoginDTO dto = new LoginDTO();
        dto.setUsername(u);
        dto.setPassword(p);
        return dto;
    }

    private static RegisterDTO registerDto(String u, String p, String c) {
        RegisterDTO dto = new RegisterDTO();
        dto.setUsername(u);
        dto.setPassword(p);
        dto.setConfirmPassword(c);
        return dto;
    }

    private static UserAccount account(Long id, String username, String rawPassword, int status) {
        return UserAccount.builder()
                .id(id)
                .username(username)
                .passwordHash(PasswordHasher.hash(rawPassword))
                .realName(username)
                .role(AuthConstants.ROLE_USER)
                .status(status)
                .build();
    }
}
