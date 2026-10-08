package com.paperaigc.detect.service;

import com.paperaigc.detect.domain.dto.AdminAccountCreateDTO;
import com.paperaigc.detect.domain.dto.AdminAccountQueryDTO;
import com.paperaigc.detect.domain.dto.AdminAccountUpdateDTO;
import com.paperaigc.detect.domain.vo.AdminAccountStatsVO;
import com.paperaigc.detect.domain.vo.AdminAccountVO;
import com.paperaigc.detect.domain.vo.PageVO;

import java.util.List;

/**
 * 运营后台 · 平台账号管理（auth_user）
 *
 * <p>与 {@link IAdminUserService}（user_profile 画像）不同，这里管的是登录凭据：停用 / 启用、重置密码、改角色、新建。</p>
 */
public interface IAdminAccountService {

    /**
     * 分页列表（SQL 分页，带检测数 / 最近检测）
     * @param query 关键字 / 角色 / 状态 / 排序 / 分页
     * @return 账号列表（不含密码）
     */
    PageVO<AdminAccountVO> page(AdminAccountQueryDTO query);

    /**
     * 顶部统计
     * @return 总数 / 正常 / 停用 / 今日新增 / 7 日活跃 / 按角色
     */
    AdminAccountStatsVO stats();

    /**
     * 单个账号（带检测数）
     * @param id 账号 id
     * @return 账号
     */
    AdminAccountVO detail(Long id);

    /**
     * 修改姓名 / 组织（null 表示不改）
     * @param id 账号 id
     * @param dto 姓名 / 组织
     */
    void updateProfile(Long id, AdminAccountUpdateDTO dto);

    /**
     * 停用 / 启用；停用后该账号所有在线 token 作废
     * @param id 账号 id
     * @param status 1 正常 / 0 停用
     * @param operatorId 操作者（不能停用自己）
     */
    void setStatus(Long id, int status, Long operatorId);

    /**
     * 批量停用 / 启用；自动跳过操作者自己
     * @param ids 账号 id 列表
     * @param status 1 正常 / 0 停用
     * @param operatorId 操作者
     * @return 实际更新条数
     */
    int batchStatus(List<Long> ids, int status, Long operatorId);

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
