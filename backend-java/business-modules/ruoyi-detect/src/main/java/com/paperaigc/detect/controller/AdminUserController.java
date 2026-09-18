package com.paperaigc.detect.controller;

import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 运营后台 · 用户管理 · Wave 3.e (§3.2)
 *
 * <p>W3.c 登录扩展未完成前，用户数据先走 mock；接入 sys_user 后替换即可。</p>
 */
@Slf4j
@RestController
@RequestMapping("/admin/user")
public class AdminUserController {

    private static final DateTimeFormatter FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    /** userId -> user map；W3.c 后切换到 sys_user 表 */
    private final Map<Long, Map<String, Object>> users = new ConcurrentHashMap<>();

    @PostConstruct
    void seed() {
        // 造点样例数据供后台联调
        LocalDateTime now = LocalDateTime.now();
        addUser(10001L, "phone",  "138****5678", 12, now.minusMinutes(3),   now.minusDays(45), "NORMAL");
        addUser(10002L, "wechat", "oGvz1w****",   3, now.minusHours(2),      now.minusDays(30), "NORMAL");
        addUser(10003L, "email",  "abc****@163.com", 47, now.minusMinutes(20), now.minusDays(90), "NORMAL");
        addUser(10004L, "phone",  "139****0011",  0, now.minusDays(60),      now.minusDays(60), "INACTIVE");
        addUser(10005L, "phone",  "180****9999", 250, now.minusMinutes(1),   now.minusDays(120), "SUSPICIOUS");
        addUser(10006L, "email",  "test****@qq.com", 8, now.minusDays(3),    now.minusDays(20), "BANNED");
    }

    private void addUser(long id, String login, String identity, int detectCount, LocalDateTime lastLoginAt,
                         LocalDateTime registeredAt, String status) {
        Map<String, Object> u = new HashMap<>();
        u.put("id", id);
        u.put("loginType", login);
        u.put("identity", identity);
        u.put("detectCount", detectCount);
        u.put("lastLoginAt", lastLoginAt.format(FMT));
        u.put("registeredAt", registeredAt.format(FMT));
        u.put("status", status);
        users.put(id, u);
    }

    /* ==================== §3.2 列表 ==================== */

    @GetMapping("/list")
    public R<Map<String, Object>> list(
            @RequestParam(value = "loginType",   required = false) String loginType,
            @RequestParam(value = "status",      required = false) String status,
            @RequestParam(value = "keyword",     required = false) String keyword,
            @RequestParam(value = "minDetect",   required = false) Integer minDetect,
            @RequestParam(value = "maxDetect",   required = false) Integer maxDetect,
            @RequestParam(value = "pageNum",  defaultValue = "1")  int pageNum,
            @RequestParam(value = "pageSize", defaultValue = "20") int pageSize) {

        List<Map<String, Object>> all = users.values().stream()
                .filter(u -> loginType == null || loginType.isBlank() || loginType.equals(u.get("loginType")))
                .filter(u -> status    == null || status.isBlank()    || status.equals(u.get("status")))
                .filter(u -> keyword   == null || keyword.isBlank()
                        || String.valueOf(u.get("identity")).toLowerCase().contains(keyword.toLowerCase())
                        || String.valueOf(u.get("id")).contains(keyword))
                .filter(u -> minDetect == null || ((int) u.get("detectCount")) >= minDetect)
                .filter(u -> maxDetect == null || ((int) u.get("detectCount")) <= maxDetect)
                .sorted(Comparator.comparing((Map<String, Object> u) -> String.valueOf(u.get("registeredAt"))).reversed())
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

    /* ==================== 单人详情 ==================== */

    @GetMapping("/{id}")
    public R<Map<String, Object>> detail(@PathVariable Long id) {
        Map<String, Object> u = users.get(id);
        if (u == null) return R.fail(4404, "用户不存在");
        return R.ok(u);
    }

    /* ==================== 封禁 / 解封 ==================== */

    @PostMapping("/{id}/ban")
    public R<Void> ban(@PathVariable Long id) {
        return updateStatus(id, "BANNED");
    }

    @PostMapping("/{id}/unban")
    public R<Void> unban(@PathVariable Long id) {
        return updateStatus(id, "NORMAL");
    }

    private R<Void> updateStatus(Long id, String status) {
        Map<String, Object> u = users.get(id);
        if (u == null) return R.fail(4404, "用户不存在");
        u.put("status", status);
        return R.ok();
    }

    /* ==================== 供 dashboard 聚合复用 ==================== */

    public java.util.Collection<Map<String, Object>> getAllUsers() {
        return users.values();
    }

    public int countTodayNewUser() {
        String today = LocalDate.now().toString();
        return (int) users.values().stream()
                .filter(u -> String.valueOf(u.get("registeredAt")).startsWith(today))
                .count();
    }
}
