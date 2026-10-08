package com.paperaigc.detect.common.util;

import jakarta.servlet.http.HttpServletRequest;

/**
 * 取客户端 IP：经 Nginx / 网关转发时读 X-Forwarded-For 第一跳，其次 X-Real-IP，最后 remoteAddr
 */
public final class ClientIpUtils {

    private ClientIpUtils() {}

    /**
     * 解析客户端 IP
     * @param request 当前请求
     * @return IP 字符串，取不到返回 "unknown"
     */
    public static String resolve(HttpServletRequest request) {
        if (request == null) return "unknown";
        String xff = request.getHeader("X-Forwarded-For");
        if (xff != null && !xff.isBlank()) {
            String first = xff.split(",")[0].trim();
            if (!first.isEmpty() && !"unknown".equalsIgnoreCase(first)) return first;
        }
        String real = request.getHeader("X-Real-IP");
        if (real != null && !real.isBlank() && !"unknown".equalsIgnoreCase(real)) return real.trim();
        String addr = request.getRemoteAddr();
        return addr == null || addr.isBlank() ? "unknown" : addr;
    }
}
