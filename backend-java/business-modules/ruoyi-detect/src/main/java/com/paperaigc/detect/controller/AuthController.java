package com.paperaigc.detect.controller;

import cn.dev33.satoken.annotation.SaIgnore;
import lombok.extern.slf4j.Slf4j;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 认证接口 · 开发期 mock
 *
 * <p>生产走若依基座自带 Sa-Token（{@code /auth/login} 等）。
 * 本地 backend-java 单独跑 ruoyi-detect 时没有基座，此 controller 兜底：
 * <ul>
 *   <li>任意账号密码放行，密码只校验非空</li>
 *   <li>{@code admin / admin} 派 OPS_ADMIN，可进 {@code /admin/*}</li>
 *   <li>其它账号派普通 USER 角色</li>
 * </ul>
 * 若依基座接入后直接删除该 controller。</p>
 */
@Slf4j
@SaIgnore    // 登录/登出/me 走 Bearer 自校验，不经 Sa-Token 拦截；生产接入基座 auth 后移除
@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {

    /** token -> user，登录后 me 接口按 header token 反查 */
    private final Map<String, Map<String, Object>> tokenToUser = new ConcurrentHashMap<>();

    @PostMapping("/login")
    public R<Map<String, Object>> login(@RequestBody Map<String, Object> body) {
        String username = str(body, "username");
        String password = str(body, "password");
        if (username == null || username.isBlank()) return R.fail(4001, "用户名不能为空");
        if (password == null || password.isBlank()) return R.fail(4002, "密码不能为空");

        Map<String, Object> user = new HashMap<>();
        user.put("id", Math.abs(username.hashCode()) % 100000L);
        user.put("username", username);
        user.put("realName", username);
        boolean isAdmin = "admin".equalsIgnoreCase(username);
        user.put("role", isAdmin ? "OPS_ADMIN" : "USER");
        user.put("orgName", isAdmin ? "运营团队" : "AI 检测个人版");

        String token = UUID.randomUUID().toString().replace("-", "");
        tokenToUser.put(token, user);

        Map<String, Object> resp = new HashMap<>();
        resp.put("accessToken", token);
        resp.put("user", user);
        log.info("mock login ok: username={} role={} tokenPrefix={}", username, user.get("role"), token.substring(0, 8));
        return R.ok(resp);
    }

    @PostMapping("/logout")
    public R<Void> logout(@RequestHeader(value = "Authorization", required = false) String auth) {
        String token = stripBearer(auth);
        if (token != null) tokenToUser.remove(token);
        return R.ok();
    }

    @GetMapping("/me")
    public R<Map<String, Object>> me(@RequestHeader(value = "Authorization", required = false) String auth) {
        String token = stripBearer(auth);
        Map<String, Object> user = token == null ? null : tokenToUser.get(token);
        if (user == null) return R.fail(401, "未登录或 token 已失效");
        return R.ok(user);
    }

    private static String str(Map<String, Object> m, String k) {
        Object v = m == null ? null : m.get(k);
        return v == null ? null : String.valueOf(v);
    }

    private static String stripBearer(String h) {
        if (h == null || h.isBlank()) return null;
        return h.startsWith("Bearer ") ? h.substring(7) : h;
    }
}
