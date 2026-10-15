package com.paperaigc.detect.service.impl;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

/**
 * highschool-spider 常驻服务客户端（后台「立即爬取某校」时按需投任务）。
 *
 * <p>默认走定时批量刷新，不常驻；此客户端只在后台点「立即爬取」时用，服务未起时记录失败即可，不抛。</p>
 */
@Slf4j
@Component
public class CrawlerClient {

    @Value("${platform.crawler.host:localhost}")
    private String host;

    @Value("${platform.crawler.port:8200}")
    private int port;

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final HttpClient http = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(3))
            .build();

    /**
     * 从爬取服务拉候选（人工审核前的原始候选）。失败返回空列表，不抛。
     * @param status pending / merged / rejected
     */
    @SuppressWarnings("unchecked")
    public java.util.List<java.util.Map<String, Object>> pullCandidates(String status) {
        try {
            String url = "http://" + host + ":" + port + "/api/v1/candidates?status=" + (status == null ? "pending" : status) + "&limit=500";
            HttpRequest req = HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(10)).GET().build();
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
            if (resp.statusCode() / 100 != 2) return java.util.List.of();
            Map<String, Object> body = objectMapper.readValue(resp.body(), Map.class);
            Object list = body.get("candidates");
            return list instanceof java.util.List ? (java.util.List<java.util.Map<String, Object>>) list : java.util.List.of();
        } catch (Exception e) {
            log.warn("pull candidates failed: {}", e.getMessage());
            return java.util.List.of();
        }
    }

    /**
     * 投一个爬取任务。
     * @return 服务返回的 jobId 文本，失败返回 null（不抛，后台记 lastStatus）
     */
    public String submit(Long schoolId, String schoolName, String entryUrl, String adapter, boolean deep) {
        try {
            Map<String, Object> body = new HashMap<>();
            body.put("entry_url", entryUrl);
            body.put("school_id", schoolId == null ? "" : String.valueOf(schoolId));
            body.put("school_name", schoolName == null ? "" : schoolName);
            body.put("adapter", adapter == null || adapter.isBlank() ? "generic" : adapter);
            body.put("deep", deep);
            HttpRequest req = HttpRequest.newBuilder(URI.create("http://" + host + ":" + port + "/api/v1/crawl"))
                    .timeout(Duration.ofSeconds(8))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(objectMapper.writeValueAsString(body)))
                    .build();
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
            if (resp.statusCode() / 100 == 2) {
                log.info("crawl job submitted school={} resp={}", schoolId, resp.body());
                return resp.body();
            }
            log.warn("crawl submit non-2xx school={} code={}", schoolId, resp.statusCode());
        } catch (Exception e) {
            log.warn("crawl submit failed school={}: {}", schoolId, e.getMessage());
        }
        return null;
    }
}
