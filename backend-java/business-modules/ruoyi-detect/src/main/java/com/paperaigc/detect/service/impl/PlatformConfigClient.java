package com.paperaigc.detect.service.impl;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Map;

/**
 * 平台参数配置客户端：透传推理服务 /api/v1/admin/config 三个接口（配置页数据源）。
 *
 * <p>鉴权在 Java 侧（/admin/platform/* 走运营后台权限），推理服务只监听内网 8000 不对外。</p>
 */
@Slf4j
@Component
public class PlatformConfigClient {

    @Value("${platform.assistant.base-url:http://localhost:8000}")
    private String baseUrl;

    private final ObjectMapper mapper = new ObjectMapper();
    private final HttpClient http = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)   // uvicorn 不支持 h2c，JDK 默认 HTTP/2 upgrade 会偶发连接损坏（422 坏 body）
            .connectTimeout(Duration.ofSeconds(5))
            .build();

    /** GET 当前配置（检测模型 + 助手 LLM），失败返回 null（配置页展示「推理服务不可达」） */
    public JsonNode getConfig() {
        return exchange("GET", "/api/v1/admin/config", null);
    }

    /** POST 切换检测模型（推理服务同步重载 checkpoint，耗时数秒到十几秒）；失败抛 IllegalStateException 带推理服务原始原因 */
    public JsonNode switchModel(Map<String, Object> body) {
        return exchange("POST", "/api/v1/admin/model/switch", body);
    }

    /** POST 更新助手 LLM 配置；失败抛 IllegalStateException 带推理服务原始原因 */
    public JsonNode updateAssistantConfig(Map<String, Object> body) {
        return exchange("POST", "/api/v1/admin/assistant/config", body);
    }

    private JsonNode exchange(String method, String path, Map<String, Object> body) {
        try {
            HttpRequest.Builder req = HttpRequest.newBuilder(URI.create(baseUrl + path))
                    .timeout(Duration.ofSeconds(90))   // 模型热切换包含 GPU 重载
                    .header("Content-Type", "application/json");
            if ("POST".equals(method)) {
                req.POST(HttpRequest.BodyPublishers.ofString(mapper.writeValueAsString(body)));
            } else {
                req.GET();
            }
            HttpResponse<String> resp = http.send(req.build(), HttpResponse.BodyHandlers.ofString());
            if (resp.statusCode() >= 400) {
                // 透出推理服务的原始错误（FastAPI {detail: "..."}），不让前端只看到笼统文案
                String detail = resp.body();
                try {
                    JsonNode d = mapper.readTree(resp.body()).path("detail");
                    if (d.isTextual()) detail = d.asText();
                } catch (Exception ignore) { /* 非 JSON 响应体原样返回 */ }
                throw new IllegalStateException(detail);
            }
            return mapper.readTree(resp.body());
        } catch (IllegalStateException e) {
            throw e;
        } catch (Exception e) {
            log.warn("platform config {} {} failed: {}", method, path, e.toString());
            throw new IllegalStateException("推理服务不可达：" + e.getMessage(), e);
        }
    }
}
