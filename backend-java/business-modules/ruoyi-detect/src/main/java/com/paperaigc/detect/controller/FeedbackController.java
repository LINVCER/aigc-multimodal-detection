package com.paperaigc.detect.controller;

import com.paperaigc.detect.common.constant.FeedbackConstants;
import com.paperaigc.detect.domain.dto.FeedbackHandleDTO;
import com.paperaigc.detect.domain.dto.FeedbackQueryDTO;
import com.paperaigc.detect.domain.dto.FeedbackSubmitDTO;
import com.paperaigc.detect.domain.vo.FeedbackVO;
import com.paperaigc.detect.domain.vo.PageVO;
import cn.dev33.satoken.annotation.SaIgnore;
import com.paperaigc.detect.service.IFeedbackService;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.paperaigc.detect.service.IHardSampleService;
import com.paperaigc.detect.domain.entity.HardSample;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import java.util.List;
import java.util.LinkedHashMap;
import java.util.Arrays;
import java.time.LocalDate;

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
    private final IHardSampleService hardSampleService;
    private final ObjectMapper objectMapper = new ObjectMapper();

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

    /* ==================== 误判样本池（增长闭环 §2.2） ==================== */

    /** 某条申诉勾选的段落样本（含当时概率；文本仅授权时有） */
    @GetMapping("/admin/feedback/{id}/samples")
    public R<List<HardSample>> samples(@PathVariable Long id) {
        return R.ok(hardSampleService.listByFeedback(id));
    }

    /** 运营复核：confirm_fp（确认误判）/ confirm_tp（确认是 AI）/ unsure */
    @PostMapping("/admin/hard-samples/{sampleId}/verdict")
    public R<Void> verdict(@PathVariable Long sampleId,
                           @RequestParam("value") String value,
                           @RequestParam(value = "reviewer", required = false) Long reviewer) {
        hardSampleService.setVerdict(sampleId, value, reviewer);
        return R.ok();
    }

    /** 样本池列表：verdict = pending / confirm_fp / confirm_tp / unsure / 空=全部 */
    @GetMapping("/admin/hard-samples")
    public R<List<HardSample>> hardSamples(@RequestParam(value = "verdict", required = false) String verdict,
                                           @RequestParam(value = "days", defaultValue = "90") int days,
                                           @RequestParam(value = "limit", defaultValue = "200") int limit) {
        return R.ok(hardSampleService.list(verdict, days, limit));
    }

    /**
     * 导出已复核且有授权文本的样本为 JSONL（一行一条），交给 ml/datasets/text/build_appeal_evalset.py 转评测集
     * 字段：text / verdict / model_prob / model_version / scenario / task_id / paragraph_idx / sample_id
     */
    @GetMapping(value = "/admin/hard-samples/export", produces = "application/x-ndjson;charset=UTF-8")
    public ResponseEntity<String> exportHardSamples(
            @RequestParam(value = "verdicts", defaultValue = "confirm_fp,confirm_tp") String verdicts) {
        List<String> vs = Arrays.stream(verdicts.split(",")).map(String::trim).filter(v -> !v.isEmpty()).toList();
        List<HardSample> rows = hardSampleService.listForExport(vs);
        StringBuilder sb = new StringBuilder();
        for (HardSample s : rows) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("sample_id", s.getId());
            m.put("text", s.getText());
            m.put("verdict", s.getOpsVerdict());
            m.put("user_label", s.getUserLabel());
            m.put("model_prob", s.getModelProb());
            m.put("model_version", s.getModelVersion());
            m.put("scenario", s.getScenario());
            m.put("task_id", s.getTaskId());
            m.put("paragraph_idx", s.getParagraphIdx());
            m.put("source", s.getSource());
            try {
                sb.append(objectMapper.writeValueAsString(m)).append('\n');
            } catch (Exception ignore) { /* 单条序列化失败跳过 */ }
        }
        String name = "appeal-samples-" + LocalDate.now() + ".jsonl";
        return ResponseEntity.ok()
                .header("Content-Disposition", "attachment; filename=\"" + name + "\"")
                .body(sb.toString());
    }

    /* 提示：状态字面量集中在 {@link FeedbackConstants}，不在 controller 硬编码 */
}
