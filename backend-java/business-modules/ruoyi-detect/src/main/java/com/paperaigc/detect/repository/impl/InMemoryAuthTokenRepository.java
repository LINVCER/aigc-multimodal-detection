package com.paperaigc.detect.repository.impl;

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import com.paperaigc.detect.domain.entity.AuthUser;
import com.paperaigc.detect.repository.IAuthTokenRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Repository;

import java.time.Duration;
import java.util.Optional;

/**
 * 内存 token 仓储：platform.auth.token-ttl-days 内有访问即续期，闲置到期自动失效。
 */
@Repository
public class InMemoryAuthTokenRepository implements IAuthTokenRepository {

    private final Cache<String, AuthUser> store;

    public InMemoryAuthTokenRepository(@Value("${platform.auth.token-ttl-days:7}") int ttlDays) {
        this.store = Caffeine.newBuilder()
                .expireAfterAccess(Duration.ofDays(Math.max(1, ttlDays)))
                .maximumSize(200_000)
                .build();
    }

    @Override
    public void put(String token, AuthUser user) {
        if (token != null && user != null) store.put(token, user);
    }

    @Override
    public Optional<AuthUser> get(String token) {
        return Optional.ofNullable(token == null ? null : store.getIfPresent(token));
    }

    @Override
    public void remove(String token) {
        if (token != null) store.invalidate(token);
    }
}
