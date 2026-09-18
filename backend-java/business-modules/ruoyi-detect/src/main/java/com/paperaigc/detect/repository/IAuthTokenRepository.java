package com.paperaigc.detect.repository;

import com.paperaigc.detect.domain.entity.AuthUser;

import java.util.Optional;

/**
 * 认证 token 存储
 *
 * <p>Phase 0 内存 map；Sa-Token 接入后由 Sa-Token session 承接，本仓储可弃用。</p>
 */
public interface IAuthTokenRepository {
    void put(String token, AuthUser user);
    Optional<AuthUser> get(String token);
    void remove(String token);
}
