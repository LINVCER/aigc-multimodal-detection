package com.paperaigc.detect.controller;

import lombok.extern.slf4j.Slf4j;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 用户反馈 · Wave 3.d
 *
 * <p>C 端提交渠道：Profile 页反馈弹窗 · 报告详情页结果申诉入口</p>
 * <p>后台入口：{@code /admin/feedback/list} 列表 + {@code /admin/feedback/{id}/handle} 回复</p>
 * <p>Phase 0：内存 Map；上生产切 user_feedback 表（见 {@code scripts/patch-schema.sql}）</p>
 */
@Slf4j
@RestController
@RequestMapping
public class FeedbackController {

    private static final Set<String> CATEGORIES = Set.of("bug", "suggestion", "appeal");
    private static final Set<String> STATUSES = Set.of("PENDING", "PROCESSING", "REPLIED", "IGNORED");
    private static final DateTimeFormatter FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final Map<Long, Map<String, Object>> feedbacks = new ConcurrentHashMap<>();
    private final AtomicLong idGen = new AtomicLong(1000);

    /* ==================== C 端 ==================== */

    /** C 端提交反馈；appeal 时应带 taskId，其余分类可选 */
    @PostMapping("/api/v1/feedback")
    public R<Map<String, Object>> submit(@RequestBody Map<String, Object> body) {
        String category = str(body, "category");
        String content  = str(body, "content");
        if (!CATEGORIES.contains(category)) return R.fail(4001, "category 必须是 bug / suggestion / appeal");
        if (content == null || content.isBlank()) return R.fail(4002, "反馈内容不能为空");
        if (content.length() > 2000) return R.fail(4003, "反馈内容超过 2000 字");

        Long taskId = numLong(body.get("taskId"));
        if ("appeal".equals(category) && taskId == null) return R.fail(4004, "结果申诉需带上 taskId");

        long id = idGen.incrementAndGet();
        Map<String, Object> fb = new HashMap<>();
        fb.put("id", id);
        // TODO(W3.c 登录接入后从 Sa-Token 上下文取 userId
        fb.put("userId", numLong(body.get("userId")));
        fb.put("category", category);
        fb.put("taskId", taskId);
        fb.put("content", content);
        fb.put("contact", str(body, "contact"));
        fb.put("status", "PENDING");
        fb.put("createdAt", LocalDateTime.now().format(FMT));
        feedbacks.put(id, fb);

        log.info("feedback submitted id={} category={} taskId={}", id, category, taskId);
        return R.ok(Map.of("id", id));
    }

    /** C 端查自己的反馈历史 */
    @GetMapping("/api/v1/feedback/mine")
    public R<List<Map<String, Object>>> mine(@RequestParam("userId") Long userId) {
        List<Map<String, Object>> list = feedbacks.values().stream()
                .filter(f -> userId.equals(f.get("userId")))
                .sorted(Comparator.comparing((Map<String, Object> f) -> String.valueOf(f.get("createdAt"))).reversed())
                .toList();
        return R.ok(list);
    }

    /* ==================== 运营后台 ==================== */

    /** 后台列表：status 过滤 + 关键字（匹配 content / contact） */
    @GetMapping("/admin/feedback/list")
    public R<Map<String, Object>> list(
            @RequestParam(value = "status", required = false) String status,
            @RequestParam(value = "keyword", required = false) String keyword,
            @RequestParam(value = "pageNum", defaultValue = "1") int pageNum,
            @RequestParam(value = "pageSize", defaultValue = "20") int pageSize) {
        List<Map<String, Object>> all = feedbacks.values().stream()
                .filter(f -> status == null || status.isBlank() || status.equals(f.get("status")))
                .filter(f -> keyword == null || keyword.isBlank()
                        || containsIgnoreCase(str(f, "content"), keyword)
                        || containsIgnoreCase(str(f, "contact"), keyword))
                .sorted(Comparator.comparing((Map<String, Object> f) -> String.valueOf(f.get("createdAt"))).reversed())
                .toList();
        int total = all.size();
        int from = Math.max(0, (pageNum - 1) * pageSize);
        int to = Math.min(total, from + pageSize);
        List<Map<String, Object>> page = from >= total ? List.of() : all.subList(from, to);

        Map<String, Object> resp = new HashMap<>();
        resp.put("total", total);
        resp.put("rows", page);
        return R.ok(resp);
    }

    /** 后台处理：写回复文本 + 置状态为 REPLIED（或运营主动置 IGNORED） */
    @PostMapping("/admin/feedback/{id}/handle")
    public R<Void> handle(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        Map<String, Object> fb = feedbacks.get(id);
        if (fb == null) return R.fail(4404, "反馈不存在");

        String newStatus = str(body, "status");
        if (newStatus == null || !STATUSES.contains(newStatus)) newStatus = "REPLIED";
        String reply = str(body, "reply");
        if ("REPLIED".equals(newStatus) && (reply == null || reply.isBlank())) {
            return R.fail(4005, "REPLIED 状态必须填回复内容");
        }

        fb.put("status", newStatus);
        fb.put("handledBy", numLong(body.get("handledBy")));
        fb.put("handledReply", reply);
        fb.put("handledAt", LocalDateTime.now().format(FMT));
        return R.ok();
    }

    /* ==================== helpers ==================== */

    private static String str(Map<String, Object> m, String k) {
        Object v = m == null ? null : m.get(k);
        return v == null ? null : String.valueOf(v);
    }

    private static Long numLong(Object o) {
        if (o == null) return null;
        if (o instanceof Number n) return n.longValue();
        try { return Long.parseLong(String.valueOf(o)); } catch (NumberFormatException e) { return null; }
    }

    private static boolean containsIgnoreCase(String s, String kw) {
        return s != null && s.toLowerCase().contains(kw.toLowerCase());
    }
}
