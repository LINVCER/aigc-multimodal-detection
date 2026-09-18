package com.paperaigc.detect.service.impl;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import com.paperaigc.detect.service.IInferenceClient;
import lombok.RequiredArgsConstructor;
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
 * HTTP 推理客户端 · 走 Python FastAPI stub 端点
 *
 * <p>gRPC server 就绪后新加 GrpcInferenceClient @Primary 顶替此 bean；此实现保留作 fallback。</p>
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class HttpInferenceClient implements IInferenceClient {

    @Value("${platform.inference.host:localhost}")
    private String host;

    @Value("${platform.inference.port:18000}")   // 对齐 deploy/inference-python 本地默认监听端口
    private int port;

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(3))
            .build();

    private String base() { return "http://" + host + ":" + port; }

    @Override
    public Map<String, Object> detectParagraph(String text, boolean returnSentences) {
        try {
            String body = objectMapper.writeValueAsString(Map.of(
                    "text", text == null ? "" : text,
                    "return_calibrated", true,
                    "return_sentences", returnSentences
            ));
            return post("/api/v1/detect/paragraph", body);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("inference detectParagraph failed", e);
            throw new BizException(ErrorCode.DETECT_INFERENCE_ERROR);
        }
    }

    @Override
    public Map<String, Object> detectAudio(byte[] audioBytes, String filename, boolean returnSegments) {
        try {
            // multipart/form-data · 手写边界（Python 侧 FastAPI File(...) 消费）
            String boundary = "----detectAudio" + System.currentTimeMillis();
            byte[] body = buildAudioMultipart(audioBytes, filename == null ? "audio.bin" : filename,
                    returnSegments, boundary);
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(base() + "/api/v1/detect/audio"))
                    .header("Content-Type", "multipart/form-data; boundary=" + boundary)
                    .timeout(Duration.ofSeconds(60))    // 音频推理可能较慢
                    .POST(HttpRequest.BodyPublishers.ofByteArray(body))
                    .build();
            HttpResponse<String> resp = httpClient.send(req, HttpResponse.BodyHandlers.ofString());
            return objectMapper.readValue(resp.body(), Map.class);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("inference detectAudio failed", e);
            throw new BizException(ErrorCode.DETECT_INFERENCE_ERROR, "音频检测服务不可用");
        }
    }

    private byte[] buildAudioMultipart(byte[] fileBytes, String filename, boolean returnSegments, String boundary)
            throws java.io.IOException {
        java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
        String head = "--" + boundary + "\r\n" +
                "Content-Disposition: form-data; name=\"file\"; filename=\"" + filename + "\"\r\n" +
                "Content-Type: application/octet-stream\r\n\r\n";
        out.write(head.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        out.write(fileBytes);
        String tail = "\r\n--" + boundary + "\r\n" +
                "Content-Disposition: form-data; name=\"return_segments\"\r\n\r\n" +
                (returnSegments ? "true" : "false") +
                "\r\n--" + boundary + "--\r\n";
        out.write(tail.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        return out.toByteArray();
    }

    @Override
    public Map<String, Object> humanize(String text, String style) {
        try {
            String body = objectMapper.writeValueAsString(Map.of(
                    "text", text == null ? "" : text,
                    "style", style == null || style.isBlank() ? "academic" : style
            ));
            return post("/api/v1/humanize", body);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("inference humanize failed", e);
            throw new BizException(ErrorCode.DETECT_INFERENCE_ERROR, "改写服务不可用");
        }
    }

    @Override
    public Map<String, Object> health() {
        try {
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(base() + "/health"))
                    .timeout(Duration.ofSeconds(3))
                    .GET().build();
            HttpResponse<String> resp = httpClient.send(req, HttpResponse.BodyHandlers.ofString());
            return objectMapper.readValue(resp.body(), Map.class);
        } catch (Exception e) {
            throw new BizException(ErrorCode.DETECT_INFERENCE_ERROR);
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> post(String path, String bodyJson) throws Exception {
        HttpRequest req = HttpRequest.newBuilder()
                .uri(URI.create(base() + path))
                .header("Content-Type", "application/json")
                .timeout(Duration.ofSeconds(15))
                .POST(HttpRequest.BodyPublishers.ofString(bodyJson))
                .build();
        HttpResponse<String> resp = httpClient.send(req, HttpResponse.BodyHandlers.ofString());
        return objectMapper.readValue(resp.body(), Map.class);
    }
}
