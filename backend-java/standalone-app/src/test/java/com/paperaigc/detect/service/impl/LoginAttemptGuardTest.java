package com.paperaigc.detect.service.impl;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 登录失败锁定单元测试
 */
@DisplayName("LoginAttemptGuard · 登录失败锁定")
class LoginAttemptGuardTest {

    @Test
    @DisplayName("达到上限前返回剩余次数，达到后锁定")
    void lockAfterMaxFailures() {
        LoginAttemptGuard guard = new LoginAttemptGuard(3, 15);
        assertThat(guard.lockedSeconds("u")).isZero();

        assertThat(guard.recordFailure("u")).isEqualTo(2);
        assertThat(guard.recordFailure("u")).isEqualTo(1);
        assertThat(guard.recordFailure("u")).isZero();       // 本次触发锁定

        assertThat(guard.lockedSeconds("u")).isGreaterThan(0);
    }

    @Test
    @DisplayName("reset 清零失败计数与锁定")
    void resetClears() {
        LoginAttemptGuard guard = new LoginAttemptGuard(2, 15);
        guard.recordFailure("u");
        guard.recordFailure("u");
        assertThat(guard.lockedSeconds("u")).isGreaterThan(0);

        guard.reset("u");
        assertThat(guard.lockedSeconds("u")).isZero();
        assertThat(guard.recordFailure("u")).isEqualTo(1);   // 重新计数
    }

    @Test
    @DisplayName("用户名按 trim + 小写归并（Admin 与 admin 同桶）")
    void caseInsensitiveKey() {
        LoginAttemptGuard guard = new LoginAttemptGuard(3, 15);
        assertThat(guard.recordFailure("Admin")).isEqualTo(2);
        assertThat(guard.recordFailure(" admin ")).isEqualTo(1);
    }

    @Test
    @DisplayName("非法配置被夹紧为最小值 1")
    void clampedConfig() {
        LoginAttemptGuard guard = new LoginAttemptGuard(0, 0);
        assertThat(guard.recordFailure("u")).isZero();       // 1 次即锁
        assertThat(guard.lockedSeconds("u")).isGreaterThan(0);
    }
}
