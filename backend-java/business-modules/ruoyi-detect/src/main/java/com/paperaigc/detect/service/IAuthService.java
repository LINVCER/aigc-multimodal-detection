package com.paperaigc.detect.service;

import com.paperaigc.detect.domain.dto.LoginDTO;
import com.paperaigc.detect.domain.entity.AuthUser;
import com.paperaigc.detect.domain.vo.LoginVO;

/**
 * 认证服务（开发期 mock）
 *
 * <p>Sa-Token 基座接入后由 Sa-Token 承接，本 Service 及其实现可删除。</p>
 */
public interface IAuthService {

    /** 登录 · 任意非空账密放行，admin/admin 派 OPS_ADMIN */
    LoginVO login(LoginDTO dto);

    /** 登出 · 清 token */
    void logout(String bearerToken);

    /** 按 header token 反查用户 */
    AuthUser me(String bearerToken);
}
