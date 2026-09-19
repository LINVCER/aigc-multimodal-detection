package com.paperaigc.detect.controller;

import cn.dev33.satoken.annotation.SaIgnore;
import com.paperaigc.detect.domain.dto.AdminUserQueryDTO;
import com.paperaigc.detect.domain.vo.AdminUserVO;
import com.paperaigc.detect.domain.vo.PageVO;
import com.paperaigc.detect.service.IAdminUserService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 运营后台 · 用户管理 · Wave 3.e (§3.2)
 *
 * <p>Controller 瘦身：参数装配 + 调 Service + 返 R；业务规则、内存 seed 全下沉。</p>
 */
@Slf4j
@SaIgnore
@RestController
@RequestMapping("/admin/user")
@RequiredArgsConstructor
public class AdminUserController {

    private final IAdminUserService adminUserService;

    @GetMapping("/list")
    public R<PageVO<AdminUserVO>> list(AdminUserQueryDTO query) {
        return R.ok(adminUserService.page(query));
    }

    @GetMapping("/{id}")
    public R<AdminUserVO> detail(@PathVariable Long id) {
        return R.ok(adminUserService.detail(id));
    }

    @PostMapping("/{id}/ban")
    public R<Void> ban(@PathVariable Long id) {
        adminUserService.ban(id);
        return R.ok();
    }

    @PostMapping("/{id}/unban")
    public R<Void> unban(@PathVariable Long id) {
        adminUserService.unban(id);
        return R.ok();
    }
}
