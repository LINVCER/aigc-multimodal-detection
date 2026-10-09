package com.paperaigc.detect.repository;

import com.paperaigc.detect.domain.entity.AdminUser;

import java.util.Collection;
import java.util.Optional;

/**
 * 后台用户仓储
 *
 * <p>Phase 0 内存 seed；Phase B 接入 sys_user + 扩展列 / 视图。</p>
 */
public interface IAdminUserRepository {
    Optional<AdminUser> findById(Long id);
    Collection<AdminUser> findAll();
    Optional<AdminUser> update(AdminUser user);
}
