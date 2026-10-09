package com.paperaigc.detect.repository.impl;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.paperaigc.detect.domain.entity.AdminUser;
import com.paperaigc.detect.mapper.AdminUserMapper;
import com.paperaigc.detect.repository.IAdminUserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Primary;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.Optional;

/**
 * user_profile 表 · MyBatis-Plus 实现（Phase B · Batch 2）
 *
 * <p>@Primary 保留以便 Phase C 引 Redis / 缓存层等新实现时无需重加。
 * seed 走 {@code R__seed_user_profile_demo.sql}（幂等）。</p>
 */
@Primary
@Repository
@RequiredArgsConstructor
public class MybatisAdminUserRepository implements IAdminUserRepository {

    private final AdminUserMapper mapper;

    @Override
    public Optional<AdminUser> findById(Long id) {
        return Optional.ofNullable(id == null ? null : mapper.selectById(id));
    }

    @Override
    public Collection<AdminUser> findAll() {
        // Service 层负责过滤/排序/分页；生产规模大时把 QueryDTO 下推 SQL
        return mapper.selectList(Wrappers.lambdaQuery(AdminUser.class)
                .orderByDesc(AdminUser::getRegisteredAt));
    }

    @Override
    public Optional<AdminUser> update(AdminUser user) {
        if (user == null || user.getId() == null) return Optional.empty();
        int n = mapper.updateById(user);
        return n > 0 ? Optional.of(user) : Optional.empty();
    }
}
