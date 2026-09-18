package com.paperaigc.detect.repository.impl;

import com.paperaigc.detect.domain.entity.AdminUser;
import com.paperaigc.detect.repository.IAdminUserRepository;
import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 后台用户内存仓储 · 含 6 条 seed 样例
 *
 * <p>seed 数据从原 AdminUserController.seed() 搬入，Phase B 接入 sys_user 后
 * 换 MybatisAdminUserRepository 顶替，seed 迁到 R__seed_admin_users.sql。</p>
 */
@Repository
public class InMemoryAdminUserRepository implements IAdminUserRepository {

    private final Map<Long, AdminUser> store = new ConcurrentHashMap<>();

    @PostConstruct
    void seed() {
        LocalDateTime now = LocalDateTime.now();
        put(10001L, "phone",  "138****5678", 12,  now.minusMinutes(3),  now.minusDays(45),  "NORMAL");
        put(10002L, "wechat", "oGvz1w****",  3,   now.minusHours(2),    now.minusDays(30),  "NORMAL");
        put(10003L, "email",  "abc****@163.com", 47, now.minusMinutes(20), now.minusDays(90), "NORMAL");
        put(10004L, "phone",  "139****0011", 0,   now.minusDays(60),    now.minusDays(60),  "INACTIVE");
        put(10005L, "phone",  "180****9999", 250, now.minusMinutes(1),  now.minusDays(120), "SUSPICIOUS");
        put(10006L, "email",  "test****@qq.com", 8, now.minusDays(3),   now.minusDays(20),  "BANNED");
    }

    private void put(long id, String login, String identity, int detectCount,
                     LocalDateTime lastLoginAt, LocalDateTime registeredAt, String status) {
        store.put(id, AdminUser.builder()
                .id(id).loginType(login).identity(identity)
                .detectCount(detectCount)
                .lastLoginAt(lastLoginAt).registeredAt(registeredAt)
                .status(status).build());
    }

    @Override
    public Optional<AdminUser> findById(Long id) {
        return Optional.ofNullable(id == null ? null : store.get(id));
    }

    @Override
    public Collection<AdminUser> findAll() {
        return store.values();
    }

    @Override
    public Optional<AdminUser> update(AdminUser user) {
        if (user == null || user.getId() == null || !store.containsKey(user.getId())) return Optional.empty();
        store.put(user.getId(), user);
        return Optional.of(user);
    }
}
