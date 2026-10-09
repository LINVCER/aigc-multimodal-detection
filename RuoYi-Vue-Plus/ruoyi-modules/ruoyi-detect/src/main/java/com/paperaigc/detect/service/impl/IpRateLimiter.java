package com.paperaigc.detect.service.impl;

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 按 IP 的分钟级计数限流（进程内存，Caffeine 固定窗口）
 *
 * <p>给未登录的公开接口用（用户名查重、验证码等），防止脚本批量探测。
 * 窗口 1 分钟写入后过期，多实例部署请换 Redis 计数。</p>
 */
@Component
public class IpRateLimiter {

    private final Cache<String, AtomicInteger> counters = Caffeine.newBuilder()
            .expireAfterWrite(Duration.ofMinutes(1))
            .maximumSize(200_000)
            .build();

    /**
     * 计一次并校验；超限抛 AUTH_RATE_LIMITED
     * @param scope 接口标识，如 "username-check"
     * @param ip 客户端 IP
     * @param perMinute 每分钟上限，≤ 0 表示不限
     */
    public void check(String scope, String ip, int perMinute) {
        if (perMinute <= 0) return;
        String key = scope + ":" + (ip == null ? "unknown" : ip);
        int n = counters.get(key, k -> new AtomicInteger()).incrementAndGet();
        if (n > perMinute) {
            throw new BizException(ErrorCode.AUTH_RATE_LIMITED);
        }
    }
}
