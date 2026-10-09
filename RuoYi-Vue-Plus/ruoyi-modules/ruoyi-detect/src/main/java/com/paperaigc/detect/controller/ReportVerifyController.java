package com.paperaigc.detect.controller;

import cn.dev33.satoken.annotation.SaIgnore;
import com.paperaigc.detect.common.util.ClientIpUtils;
import com.paperaigc.detect.domain.vo.ReportVerifyVO;
import com.paperaigc.detect.service.IReportCredentialService;
import com.paperaigc.detect.service.impl.IpRateLimiter;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.dromara.common.core.domain.R;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 报告真伪验证（公开，不需登录；按 IP 限流防爆破）
 */
@SaIgnore
@RestController
@RequestMapping("/api/v1/verify")
@RequiredArgsConstructor
public class ReportVerifyController {

    private final IReportCredentialService credentialService;
    private final IpRateLimiter rateLimiter;

    @Value("${platform.report.verify-per-minute:30}")
    private int verifyPerMinute;

    /** 扫码 / 链接直达：/api/v1/verify/{reportNo}?code=xxx */
    @GetMapping("/{reportNo}")
    public R<ReportVerifyVO> verify(@PathVariable String reportNo, @RequestParam("code") String code, HttpServletRequest request) {
        rateLimiter.check("report-verify", ClientIpUtils.resolve(request), verifyPerMinute);
        return R.ok(credentialService.verify(reportNo, code));
    }

    /** 表单提交：body { reportNo, code } */
    @PostMapping
    public R<ReportVerifyVO> verifyPost(@RequestBody Map<String, String> body, HttpServletRequest request) {
        rateLimiter.check("report-verify", ClientIpUtils.resolve(request), verifyPerMinute);
        return R.ok(credentialService.verify(body.get("reportNo"), body.get("code")));
    }
}
