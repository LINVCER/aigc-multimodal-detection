package com.paperaigc.detect.service;

import com.paperaigc.detect.domain.dto.ChangePasswordDTO;
import com.paperaigc.detect.domain.dto.LoginDTO;
import com.paperaigc.detect.domain.dto.RegisterDTO;
import com.paperaigc.detect.domain.entity.AuthUser;
import com.paperaigc.detect.domain.vo.LoginVO;

/**
 * 认证服务
 *
 * <p>账号密码登录 + 注册走 auth_user 表（salt + SHA-256）；微信一键登录 mock；token 内存仓储。</p>
 */
public interface IAuthService {

    /** 登录 · 验证码 + 失败锁定 + 查 auth_user 表校验；admin/admin 兜底自动建管理员 */
    LoginVO login(LoginDTO dto);

    /** 注册 · 用户名唯一 + 密码策略 + hash 落库，注册即登录 */
    LoginVO register(RegisterDTO dto);

    /**
     * 修改密码 · 校验原密码与新密码策略，成功后当前 token 作废
     * @param bearerToken Authorization header
     * @param dto 原密码 / 新密码 / 确认
     */
    void changePassword(String bearerToken, ChangePasswordDTO dto);

    /**
     * 微信一键登录（mock）
     * <p>生产接入需 code2session：wx.login → code → openid/session_key。
     * 当前 mock 用 code 派生 userId，返 LoginVO。</p>
     * @param code wx.login 拿到的临时 code
     * @param nickname 用户昵称（可选 · wx.getUserProfile 拿）
     * @param avatarUrl 头像 URL（可选）
     */
    LoginVO loginByWechat(String code, String nickname, String avatarUrl);

    /** 登出 · 清 token */
    void logout(String bearerToken);

    /** 按 header token 反查用户 */
    AuthUser me(String bearerToken);
}
