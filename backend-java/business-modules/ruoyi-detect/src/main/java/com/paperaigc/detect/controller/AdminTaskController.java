package com.paperaigc.detect.controller;

import lombok.extern.slf4j.Slf4j;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 运营后台 · 全平台任务列表 · Wave 3.e (§3.4)
 *
 * <p>无 org 过滤跨用户查询；数据从 {@link DetectController} 内存 map 取，
 * 后续切 Service+DB 时保留 admin 分层不变。</p>
 */
@Slf4j
@RestController
@RequestMapping("/admin/task")
public class AdminTaskController {

    private final DetectController detectController;
    private final AdminUserController adminUserController;

    public AdminTaskController(DetectController detectController, AdminUserController adminUserController) {
        this.detectController = detectController;
        this.adminUserController = adminUserController;
    }

    @GetMapping("/list")
    public R<Map<String, Object>> list(
            @RequestParam(value = "status",    required = false) String status,
            @RequestParam(value = "scenario",  required = false) String scenario,
            @RequestParam(value = "userId",    required = false) Long userId,
            @RequestParam(value = "keyword",   required = false) String keyword,
            @RequestParam(value = "minAiRate", required = false) Double minAiRate,
            @RequestParam(value = "maxAiRate", required = false) Double maxAiRate,
            @RequestParam(value = "pageNum",  defaultValue = "1")  int pageNum,
            @RequestParam(value = "pageSize", defaultValue = "20") int pageSize) {

        List<Map<String, Object>> all = detectController.getAllTasksRaw().stream()
                .filter(t -> status    == null || status.isBlank()    || status.equals(t.get("status")))
                .filter(t -> scenario  == null || scenario.isBlank()  || scenario.equals(t.get("scenario")))
                .filter(t -> userId    == null || userId.equals(numLong(t.get("userId"))))
                .filter(t -> keyword   == null || keyword.isBlank()
                        || String.valueOf(t.getOrDefault("paperTitle", "")).toLowerCase().contains(keyword.toLowerCase()))
                .filter(t -> minAiRate == null || (aiRate(t) != null && aiRate(t) >= minAiRate))
                .filter(t -> maxAiRate == null || (aiRate(t) != null && aiRate(t) <= maxAiRate))
                .sorted(Comparator.comparing((Map<String, Object> t) -> String.valueOf(t.get("createdAt"))).reversed())
                .map(this::maskForAdmin)
                .toList();

        int total = all.size();
        int from = Math.max(0, (pageNum - 1) * pageSize);
        int to   = Math.min(total, from + pageSize);
        List<Map<String, Object>> rows = from >= total ? List.of() : all.subList(from, to);

        Map<String, Object> resp = new HashMap<>();
        resp.put("total", total);
        resp.put("rows", rows);
        return R.ok(resp);
    }

    /**
     * 运营视图：不返回原文段落，只带列表字段 + 用户脱敏标识。
     * 想看段落细节走 C 端相同的 GET /api/v1/detect/tasks/{id}。
     */
    private Map<String, Object> maskForAdmin(Map<String, Object> t) {
        Map<String, Object> m = new HashMap<>();
        m.put("id",          t.get("id"));
        m.put("paperTitle",  t.get("paperTitle"));
        m.put("scenario",    t.get("scenario"));
        m.put("threshold",   t.get("threshold"));
        m.put("aiRate",      t.get("aiRate"));
        m.put("status",      t.get("status"));
        m.put("createdAt",   t.get("createdAt"));
        m.put("wordCount",   t.get("wordCount"));
        m.put("modelVersion", t.getOrDefault("modelVersion", "stub-v0"));
        Long uid = numLong(t.get("userId"));
        m.put("userId", uid);
        m.put("userLabel", uid == null ? "-" : userLabel(uid));
        return m;
    }

    private String userLabel(Long uid) {
        Map<String, Object> u = null;
        for (Map<String, Object> x : adminUserController.getAllUsers()) {
            if (uid.equals(x.get("id"))) { u = x; break; }
        }
        if (u == null) return "user#" + uid;
        return String.valueOf(u.get("identity"));
    }

    private static Double aiRate(Map<String, Object> t) {
        Object v = t.get("aiRate");
        return v instanceof Number n ? n.doubleValue() : null;
    }

    private static Long numLong(Object o) {
        if (o == null) return null;
        if (o instanceof Number n) return n.longValue();
        try { return Long.parseLong(String.valueOf(o)); } catch (NumberFormatException e) { return null; }
    }
}
