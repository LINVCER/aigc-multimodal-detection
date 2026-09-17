package com.paperaigc.detect.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.Map;

/**
 * 论文 AIGC 检测接口
 *
 * Phase 0：直接通过 HTTP 调 Python 推理 stub（localhost:8000）
 * 后续切 gRPC 时，替换为 DetectionInferenceClient（proto 已备好）
 */
@Slf4j
@RestController
@RequestMapping("/detect")
public class DetectController {

    /** Python 推理服务地址（Phase 0 stub） */
    private static final String INFERENCE_BASE = "http://localhost:18000";

    private final HttpClient httpClient = HttpClient.newHttpClient();
    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 单段文本检测
     */
    @PostMapping("/paragraph")
    public R<Map<String, Object>> detectParagraph(@RequestBody Map<String, String> body) {
        try {
            String text = body.getOrDefault("text", "");
            String reqJson = objectMapper.writeValueAsString(Map.of(
                    "text", text,
                    "return_calibrated", true,
                    "return_sentences", false
            ));

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(INFERENCE_BASE + "/api/v1/detect/paragraph"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(reqJson))
                    .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            Map<String, Object> result = objectMapper.readValue(response.body(), Map.class);
            return R.ok(result);
        } catch (Exception e) {
            log.error("detect paragraph failed", e);
            return R.fail("检测服务暂时不可用，请稍后重试");
        }
    }

    /**
     * 推理服务健康检查
     */
    @GetMapping("/health")
    public R<Map<String, Object>> health() {
        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(INFERENCE_BASE + "/health"))
                    .GET()
                    .build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            Map<String, Object> result = objectMapper.readValue(response.body(), Map.class);
            return R.ok(result);
        } catch (Exception e) {
            log.error("inference health check failed", e);
            return R.fail("推理服务不可用");
        }
    }
}
