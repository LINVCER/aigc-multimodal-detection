package com.paperaigc.detect.repository.impl;

import com.paperaigc.detect.domain.entity.AuthUser;
import com.paperaigc.detect.repository.IAuthTokenRepository;
import org.springframework.stereotype.Repository;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

@Repository
public class InMemoryAuthTokenRepository implements IAuthTokenRepository {

    private final Map<String, AuthUser> store = new ConcurrentHashMap<>();

    @Override
    public void put(String token, AuthUser user) {
        if (token != null && user != null) store.put(token, user);
    }

    @Override
    public Optional<AuthUser> get(String token) {
        return Optional.ofNullable(token == null ? null : store.get(token));
    }

    @Override
    public void remove(String token) {
        if (token != null) store.remove(token);
    }
}
