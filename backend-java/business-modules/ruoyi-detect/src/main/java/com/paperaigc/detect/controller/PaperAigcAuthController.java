package com.paperaigc.detect.controller;

import cn.dev33.satoken.annotation.SaIgnore;
import com.paperaigc.detect.common.constant.AuthConstants;
import com.paperaigc.detect.domain.dto.LoginDTO;
import com.paperaigc.detect.domain.entity.AuthUser;
import com.paperaigc.detect.domain.vo.LoginVO;
import com.paperaigc.detect.service.IAuthService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 认证接口 · 开发期 mock
 *
 * <p>规则见 {@link IAuthService}；生产走若依基座自带 Sa-Token，本 Controller + Service 可整体删除。</p>
 */
@Slf4j
@SaIgnore
@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class PaperAigcAuthController {

    private final IAuthService authService;

    @PostMapping("/login")
    public R<LoginVO> login(@Valid @RequestBody LoginDTO dto) {
        return R.ok(authService.login(dto));
    }

    /**
     * 微信一键登录（Wave 3.1 · mock）
     * body 期望 { code, nickname?, avatarUrl? }
     */
    @PostMapping("/wechat/login")
    public R<LoginVO> wechatLogin(@RequestBody java.util.Map<String, String> body) {
        return R.ok(authService.loginByWechat(
                body.get("code"), body.get("nickname"), body.get("avatarUrl")));
    }

    @PostMapping("/logout")
    public R<Void> logout(@RequestHeader(value = AuthConstants.HEADER_AUTHORIZATION, required = false) String auth) {
        authService.logout(auth);
        return R.ok();
    }

    @GetMapping("/me")
    public R<AuthUser> me(@RequestHeader(value = AuthConstants.HEADER_AUTHORIZATION, required = false) String auth) {
        return R.ok(authService.me(auth));
    }
}
