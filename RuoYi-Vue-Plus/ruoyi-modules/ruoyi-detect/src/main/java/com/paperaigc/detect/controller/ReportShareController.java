package com.paperaigc.detect.controller;

import cn.dev33.satoken.annotation.SaIgnore;
import com.paperaigc.detect.common.constant.AuthConstants;
import com.paperaigc.detect.domain.dto.CreateShareDTO;
import com.paperaigc.detect.domain.entity.AuthUser;
import com.paperaigc.detect.domain.vo.ReportShareVO;
import com.paperaigc.detect.domain.vo.SharedReportVO;
import com.paperaigc.detect.service.IAuthService;
import com.paperaigc.detect.service.IReportShareService;
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

import java.util.List;

/**
 * 报告只读分享
 *
 * <p>所有者侧挂在 /api/v1/report/...；公开读取在 /api/v1/share/{token}，不需要登录。</p>
 */
@SaIgnore
@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class ReportShareController {

    private final IReportShareService shareService;
    private final IAuthService authService;

    @PostMapping("/report/tasks/{id}/share")
    public R<ReportShareVO> create(@PathVariable Long id,
                                   @RequestBody(required = false) @Valid CreateShareDTO dto,
                                   @RequestParam(value = "userId", required = false) Long userId,   // W3.c 前透传
                                   @RequestHeader(value = AuthConstants.HEADER_AUTHORIZATION, required = false) String auth) {
        Long owner = userId != null ? userId : currentUserId(auth);
        return R.ok(shareService.create(id, dto == null ? new CreateShareDTO() : dto, owner));
    }

    @GetMapping("/report/tasks/{id}/shares")
    public R<List<ReportShareVO>> list(@PathVariable Long id) {
        return R.ok(shareService.list(id));
    }

    @PostMapping("/report/share/{token}/revoke")
    public R<Void> revoke(@PathVariable String token) {
        shareService.revoke(token);
        return R.ok();
    }

    /** 公开只读报告 */
    @GetMapping("/share/{token}")
    public R<SharedReportVO> view(@PathVariable String token) {
        return R.ok(shareService.view(token));
    }

    private Long currentUserId(String auth) {
        try {
            AuthUser u = authService.me(auth);
            return u == null ? null : u.getId();
        } catch (Exception e) {
            return null;
        }
    }
}
