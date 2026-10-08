package com.paperaigc.detect.service;

import com.paperaigc.detect.domain.dto.AdminAccountCreateDTO;
import com.paperaigc.detect.domain.dto.AdminAccountQueryDTO;
import com.paperaigc.detect.domain.vo.AdminAccountVO;
import com.paperaigc.detect.domain.vo.PageVO;

/**
 * 运营后台 · 平台账号管理（auth_user）
 *
 * <p>与 {@link IAdminUserService}（user_profile 画像）不同，这里管的是登录凭据：停用 / 启用、重置密码、改角色、新建。</p>
 */
public interface IAdminAccountService {

    /**
     * 分页列表
     * @param query 关键字 / 角色 / 状态 / 分页
     * @return 账号列表（不含密码）
     */
    PageVO<AdminAccountVO> page(AdminAccountQueryDTO query);

    /**
     * 停用 / 启用；停用后该账号所有在线 token 作废
     * @param id 账号 id
     * @param status 1 正常 / 0 停用
     * @param operatorId 操作者（不能停用自己）
     */
    void setStatus(Long id, int status, Long operatorId);

    /**
     * 重置密码：生成一次性临时密码并作废该账号在线 token
     * @param id 账号 id
     * @return 临时密码明文（只返回这一次）
     */
    String resetPassword(Long id);

    /**
     * 改角色
     * @param id 账号 id
     * @param role USER / ADMIN / OPS_ADMIN
     * @param operatorId 操作者（不能改自己）
     */
    void setRole(Long id, String role, Long operatorId);

    /**
     * 新建账号（管理员代开）
     * @param dto 用户名 / 姓名 / 角色 / 组织
     * @return 临时密码明文
     */
    String create(AdminAccountCreateDTO dto);
}
