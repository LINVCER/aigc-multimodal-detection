package com.paperaigc.detect.controller;

import cn.dev33.satoken.annotation.SaIgnore;
import com.paperaigc.detect.common.constant.AuthConstants;
import com.paperaigc.detect.domain.dto.AdminAccountCreateDTO;
import com.paperaigc.detect.domain.dto.AdminAccountQueryDTO;
import com.paperaigc.detect.domain.entity.AuthUser;
import com.paperaigc.detect.domain.vo.AdminAccountVO;
import com.paperaigc.detect.domain.vo.PageVO;
import com.paperaigc.detect.service.IAdminAccountService;
import com.paperaigc.detect.service.IAuthService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 运营后台 · 平台账号管理（auth_user）
 */
@SaIgnore
@RestController
@RequestMapping("/admin/account")
@RequiredArgsConstructor
public class AdminAccountController {

    private final IAdminAccountService accountService;
    private final IAuthService authService;

    @GetMapping("/list")
    public R<PageVO<AdminAccountVO>> list(AdminAccountQueryDTO query) {
        return R.ok(accountService.page(query));
    }

    /** 停用 / 启用：status=0 / 1 */
    @PostMapping("/{id}/status")
    public R<Void> setStatus(@PathVariable Long id, @RequestParam int status,
                             @RequestHeader(value = AuthConstants.HEADER_AUTHORIZATION, required = false) String auth) {
        accountService.setStatus(id, status, operatorId(auth));
        return R.ok();
    }

    /** 重置密码，临时密码只在本次响应里返回 */
    @PostMapping("/{id}/reset-password")
    public R<Map<String, String>> resetPassword(@PathVariable Long id) {
        return R.ok(Map.of("tempPassword", accountService.resetPassword(id)));
    }

    @PostMapping("/{id}/role")
    public R<Void> setRole(@PathVariable Long id, @RequestParam String role,
                           @RequestHeader(value = AuthConstants.HEADER_AUTHORIZATION, required = false) String auth) {
        accountService.setRole(id, role, operatorId(auth));
        return R.ok();
    }

    @PostMapping
    public R<Map<String, String>> create(@Valid @RequestBody AdminAccountCreateDTO dto) {
        return R.ok(Map.of("tempPassword", accountService.create(dto)));
    }

    private Long operatorId(String auth) {
        try {
            AuthUser u = authService.me(auth);
            return u == null ? null : u.getId();
        } catch (Exception e) {
            return null;
        }
    }
}
