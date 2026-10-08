package com.paperaigc.detect.controller;

import cn.dev33.satoken.annotation.SaIgnore;
import com.paperaigc.detect.domain.dto.DetectTaskQueryDTO;
import com.paperaigc.detect.domain.vo.PageVO;
import com.paperaigc.detect.service.IAdminTaskService;
import lombok.RequiredArgsConstructor;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * 运营后台 · 全平台任务 · Wave 3.e (§3.4)
 *
 * <p>单条重试 / 取消 / 删除复用 /api/v1/detect/tasks/{id}/... ；这里只提供列表、统计与批量。</p>
 */
@SaIgnore
@RestController
@RequestMapping("/admin/task")
@RequiredArgsConstructor
public class AdminTaskController {

    private final IAdminTaskService adminTaskService;

    @GetMapping("/list")
    public R<PageVO<Map<String, Object>>> list(DetectTaskQueryDTO q) {
        return R.ok(adminTaskService.page(q));
    }

    @GetMapping("/stats")
    public R<Map<String, Object>> stats() {
        return R.ok(adminTaskService.stats());
    }

    /** body { ids: [...] } */
    @PostMapping("/batch-delete")
    public R<Map<String, Integer>> batchDelete(@RequestBody Map<String, Object> body) {
        return R.ok(Map.of("deleted", adminTaskService.batchDelete(ids(body))));
    }

    /** body { ids: [...] }，只对 FAILED 生效 */
    @PostMapping("/batch-retry")
    public R<Map<String, Integer>> batchRetry(@RequestBody Map<String, Object> body) {
        return R.ok(Map.of("retried", adminTaskService.batchRetry(ids(body))));
    }

    private static List<Long> ids(Map<String, Object> body) {
        Object raw = body == null ? null : body.get("ids");
        return raw instanceof List<?> l ? l.stream().filter(Number.class::isInstance).map(x -> ((Number) x).longValue()).toList() : List.of();
    }
}
