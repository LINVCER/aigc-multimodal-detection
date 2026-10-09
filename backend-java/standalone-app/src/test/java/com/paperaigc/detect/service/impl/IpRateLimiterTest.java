package com.paperaigc.detect.service.impl;

import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * IP 分钟级限流单元测试
 */
@DisplayName("IpRateLimiter · IP 限流")
class IpRateLimiterTest {

    @Test
    @DisplayName("未超限放行，超限抛 AUTH_RATE_LIMITED")
    void limit() {
        IpRateLimiter limiter = new IpRateLimiter();
        assertThatCode(() -> limiter.check("username-check", "1.1.1.1", 2)).doesNotThrowAnyException();
        assertThatCode(() -> limiter.check("username-check", "1.1.1.1", 2)).doesNotThrowAnyException();

        assertThatThrownBy(() -> limiter.check("username-check", "1.1.1.1", 2))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode())
                .isEqualTo(ErrorCode.AUTH_RATE_LIMITED.getCode());
    }

    @Test
    @DisplayName("perMinute <= 0 表示不限流")
    void unlimited() {
        IpRateLimiter limiter = new IpRateLimiter();
        assertThatCode(() -> {
            for (int i = 0; i < 100; i++) limiter.check("s", "1.1.1.1", 0);
        }).doesNotThrowAnyException();
    }

    @Test
    @DisplayName("不同 IP / 不同 scope 互不影响")
    void isolated() {
        IpRateLimiter limiter = new IpRateLimiter();
        limiter.check("s", "1.1.1.1", 1);
        assertThatCode(() -> limiter.check("s", "2.2.2.2", 1)).doesNotThrowAnyException();
        assertThatCode(() -> limiter.check("other", "1.1.1.1", 1)).doesNotThrowAnyException();
    }
}
