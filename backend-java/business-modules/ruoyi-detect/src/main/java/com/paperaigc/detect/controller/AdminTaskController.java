package com.paperaigc.detect.controller;

import com.paperaigc.detect.common.util.ParamUtils;
import com.paperaigc.detect.domain.dto.DetectTaskQueryDTO;
import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.vo.PageVO;
import com.paperaigc.detect.repository.IDetectTaskRepository;
import com.paperaigc.detect.service.IAdminUserService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 运营后台 · 全平台任务列表 · Wave 3.e (§3.4)
 */
@Slf4j
@RestController
@RequestMapping("/admin/task")
@RequiredArgsConstructor
public class AdminTaskController {

    private final IDetectTaskRepository taskRepository;
    private final IAdminUserService adminUserService;

    @GetMapping("/list")
    public R<PageVO<Map<String, Object>>> list(DetectTaskQueryDTO q) {
        List<Map<String, Object>> all = taskRepository.findAll().stream()
                .filter(t -> ParamUtils.isBlank(q.getStatus())   || q.getStatus().equals(t.getStatus()))
                .filter(t -> ParamUtils.isBlank(q.getScenario()) || q.getScenario().equals(t.getScenario()))
                .filter(t -> q.getUserId() == null || q.getUserId().equals(t.getUserId()))
                .filter(t -> ParamUtils.isBlank(q.getKeyword())
                        || ParamUtils.containsIgnoreCase(t.getPaperTitle(), q.getKeyword()))
                .filter(t -> q.getMinAiRate() == null || (t.getAiRate() != null && t.getAiRate() >= q.getMinAiRate()))
                .filter(t -> q.getMaxAiRate() == null || (t.getAiRate() != null && t.getAiRate() <= q.getMaxAiRate()))
                .sorted(Comparator.comparing(DetectTask::getCreatedAt,
                        Comparator.nullsLast(Comparator.reverseOrder())))
                .map(this::maskForAdmin)
                .toList();

        int total = all.size();
        int pageNum = q.getPageNum() == null || q.getPageNum() < 1 ? 1 : q.getPageNum();
        int pageSize = q.getPageSize() == null || q.getPageSize() < 1 ? 20 : q.getPageSize();
        int from = Math.max(0, (pageNum - 1) * pageSize);
        int to = Math.min(total, from + pageSize);
        List<Map<String, Object>> rows = from >= total ? List.of() : all.subList(from, to);
        return R.ok(PageVO.of(total, rows));
    }

    /** 运营视图：不返回原文段落，只带列表字段 + 用户脱敏标识 */
    private Map<String, Object> maskForAdmin(DetectTask t) {
        Map<String, Object> m = new HashMap<>();
        m.put("id",           t.getId());
        m.put("paperTitle",   t.getPaperTitle());
        m.put("scenario",     t.getScenario());
        m.put("threshold",    t.getThreshold());
        m.put("aiRate",       t.getAiRate());
        m.put("status",       t.getStatus());
        m.put("createdAt",    t.getCreatedAt() == null ? null : t.getCreatedAt().toString());
        m.put("wordCount",    t.getWordCount());
        m.put("modelVersion", t.getModelVersion() == null ? "stub-v0" : t.getModelVersion());
        Long uid = t.getUserId();
        m.put("userId", uid);
        m.put("userLabel", adminUserService.userLabel(uid));
        return m;
    }
}
