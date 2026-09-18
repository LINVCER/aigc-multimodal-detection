package com.paperaigc.detect.service;

import com.paperaigc.detect.domain.dto.AdminUserQueryDTO;
import com.paperaigc.detect.domain.entity.AdminUser;
import com.paperaigc.detect.domain.vo.AdminUserVO;
import com.paperaigc.detect.domain.vo.PageVO;

import java.util.Collection;

/**
 * 运营后台 · 用户管理
 */
public interface IAdminUserService {

    /** §3.2 列表 · 分页 + 多维筛选 */
    PageVO<AdminUserVO> page(AdminUserQueryDTO query);

    /** 单人详情 */
    AdminUserVO detail(Long id);

    /** 封禁 → status=BANNED */
    void ban(Long id);

    /** 解封 → status=NORMAL */
    void unban(Long id);

    /* ==================== 供 Dashboard / TaskLabel 复用 ==================== */

    /** 全量用户快照（Dashboard KPI / topUsers / userLabel 复用） */
    Collection<AdminUser> findAll();

    /** 今日新增用户数（Dashboard KPI） */
    int countTodayNewUser();

    /** 根据 userId 拿脱敏 identity（后台任务列表 userLabel 用；无匹配返 "user#{id}"） */
    String userLabel(Long userId);
}
