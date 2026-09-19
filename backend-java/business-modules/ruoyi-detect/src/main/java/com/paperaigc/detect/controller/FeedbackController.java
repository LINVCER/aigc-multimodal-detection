package com.paperaigc.detect.controller;

import com.paperaigc.detect.common.constant.FeedbackConstants;
import com.paperaigc.detect.domain.dto.FeedbackHandleDTO;
import com.paperaigc.detect.domain.dto.FeedbackQueryDTO;
import com.paperaigc.detect.domain.dto.FeedbackSubmitDTO;
import com.paperaigc.detect.domain.vo.FeedbackVO;
import com.paperaigc.detect.domain.vo.PageVO;
import cn.dev33.satoken.annotation.SaIgnore;
import com.paperaigc.detect.service.IFeedbackService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 用户反馈接口 · Wave 3.d
 *
 * <p>C 端：{@code /api/v1/feedback/*} · 后台：{@code /admin/feedback/*}</p>
 * <p>Controller 只做参数装配 + 调 Service，业务规则全部下沉到 {@link IFeedbackService}。</p>
 */
@Slf4j
@SaIgnore
@RestController
@RequestMapping
@RequiredArgsConstructor
public class FeedbackController {

    private final IFeedbackService feedbackService;

    /* ==================== C 端 ==================== */

    /** C 端提交反馈 */
    @PostMapping("/api/v1/feedback")
    public R<Map<String, Object>> submit(@Valid @RequestBody FeedbackSubmitDTO dto) {
        Long id = feedbackService.submit(dto);
        return R.ok(Map.of("id", id));
    }

    /** C 端查自己反馈历史 */
    @GetMapping("/api/v1/feedback/mine")
    public R<PageVO<FeedbackVO>> mine(@RequestParam("userId") Long userId) {
        FeedbackQueryDTO q = new FeedbackQueryDTO();
        q.setUserId(userId);
        q.setPageSize(100);
        return R.ok(feedbackService.page(q));
    }

    /* ==================== 运营后台 ==================== */

    /** 后台反馈列表（分页 + status/keyword 过滤） */
    @GetMapping("/admin/feedback/list")
    public R<PageVO<FeedbackVO>> list(FeedbackQueryDTO query) {
        return R.ok(feedbackService.page(query));
    }

    /** 后台处理反馈（回复 / 标 IGNORED / 置 PROCESSING） */
    @PostMapping("/admin/feedback/{id}/handle")
    public R<Void> handle(@PathVariable Long id, @RequestBody FeedbackHandleDTO dto) {
        feedbackService.handle(id, dto);
        return R.ok();
    }

    /* 提示：状态字面量集中在 {@link FeedbackConstants}，不在 controller 硬编码 */
}
