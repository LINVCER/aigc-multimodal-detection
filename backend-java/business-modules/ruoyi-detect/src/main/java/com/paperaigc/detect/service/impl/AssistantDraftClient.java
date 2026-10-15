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
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 反馈 AI 草稿客户端：调 Python 助手 /api/v1/assistant/draft-reply 生成回复草稿。
 *
 * <p>草稿仅供管理员参考，审核通过才会写入 handled_reply；任何失败都静默降级（返回 null），
 * 不影响用户提交反馈本身。</p>
 */
@Slf4j
@Component
public class AssistantDraftClient {

    @Value("${platform.assistant.base-url:http://localhost:8000}")
    private String baseUrl;

    private final ObjectMapper mapper = new ObjectMapper();
    private final HttpClient http = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)   // uvicorn 不支持 h2c，强制 1.1 避免升级失败连接损坏
            .connectTimeout(Duration.ofSeconds(5))
            .build();

    /**
     * 生成回复草稿。
     *
     * @param category 反馈分类（bug / suggestion / appeal）
     * @param content  反馈原文
     * @param taskId   关联检测任务（申诉类），可为 null
     * @return 草稿文本；服务不可用 / 超时 / 返回为空时返回 null
     */
    public String draftReply(String category, String content, Long taskId) {
        try {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("category", category);
            body.put("content", content);
            if (taskId != null) body.put("taskId", taskId);

            HttpRequest req = HttpRequest.newBuilder(URI.create(baseUrl + "/api/v1/assistant/draft-reply"))
                    .timeout(Duration.ofSeconds(60))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(mapper.writeValueAsString(body)))
                    .build();
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
            if (resp.statusCode() != 200) {
                log.warn("draft-reply http {} category={}", resp.statusCode(), category);
                return null;
            }
            JsonNode data = mapper.readTree(resp.body()).path("data").path("reply");
            String reply = data.isTextual() ? data.asText().trim() : "";
            return reply.isEmpty() ? null : reply;
        } catch (Exception e) {
            log.warn("draft-reply failed category={}: {}", category, e.toString());
            return null;
        }
    }
}
