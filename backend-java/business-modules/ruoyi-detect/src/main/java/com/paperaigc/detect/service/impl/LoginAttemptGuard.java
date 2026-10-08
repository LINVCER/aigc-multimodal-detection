package com.paperaigc.detect.service.impl;

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.Locale;

/**
 * 登录失败计数与临时锁定（按用户名，进程内存）
 *
 * <p>连续失败达到 platform.auth.lock-max-failures 次后锁定 platform.auth.lock-minutes 分钟；
 * 成功登录即清零。单实例部署够用，多实例请换 Redis 计数。</p>
 */
@Component
public class LoginAttemptGuard {

    private final int maxFailures;
    private final Duration lockDuration;
    private final Cache<String, Integer> failures;
    private final Cache<String, Long> lockedUntil;

    public LoginAttemptGuard(@Value("${platform.auth.lock-max-failures:5}") int maxFailures,
                             @Value("${platform.auth.lock-minutes:15}") int lockMinutes) {
        this.maxFailures = Math.max(1, maxFailures);
        this.lockDuration = Duration.ofMinutes(Math.max(1, lockMinutes));
        // 失败计数窗口与锁定时长一致：窗口内没再失败就自然归零
        this.failures = Caffeine.newBuilder().expireAfterWrite(lockDuration).maximumSize(100_000).build();
        this.lockedUntil = Caffeine.newBuilder().expireAfterWrite(lockDuration).maximumSize(100_000).build();
    }

    /**
     * 剩余锁定秒数
     * @param username 登录名
     * @return 0 表示未锁定
     */
    public long lockedSeconds(String username) {
        Long until = lockedUntil.getIfPresent(key(username));
        if (until == null) return 0;
        long left = (until - System.currentTimeMillis()) / 1000;
        if (left <= 0) {
            lockedUntil.invalidate(key(username));
            return 0;
        }
        return left;
    }

    /**
     * 记一次失败
     * @param username 登录名
     * @return 距离锁定还剩几次机会，0 表示本次已触发锁定
     */
    public int recordFailure(String username) {
        String k = key(username);
        int n = failures.asMap().merge(k, 1, Integer::sum);
        if (n >= maxFailures) {
            lockedUntil.put(k, System.currentTimeMillis() + lockDuration.toMillis());
            failures.invalidate(k);
            return 0;
        }
        return maxFailures - n;
    }

    /** 登录成功，清零 */
    public void reset(String username) {
        failures.invalidate(key(username));
        lockedUntil.invalidate(key(username));
    }

    private static String key(String username) {
        return username == null ? "" : username.trim().toLowerCase(Locale.ROOT);
    }
}
