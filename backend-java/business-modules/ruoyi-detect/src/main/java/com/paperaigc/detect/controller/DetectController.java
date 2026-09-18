package com.paperaigc.detect.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.dromara.common.core.domain.R;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 论文 AIGC 检测接口
 *
 * <p>路径遵循 docs/design/API_CONTRACT.md（§3 检测 · §4 降 AIGC · §8 内部推理）</p>
 * <p>Phase 0：HTTP 调 Python 推理 stub；数据落内存 Map。后续切 gRPC + MyBatis 时替换 service 实现。</p>
 */
@Slf4j
@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class DetectController {

    @Value("${platform.inference.host:localhost}")
    private String inferenceHost;

    @Value("${platform.inference.port:8000}")
    private int inferencePort;

    private final HttpClient httpClient = HttpClient.newHttpClient();
    private final ObjectMapper objectMapper = new ObjectMapper();

    // 内存态：任务表；生产替换为 detect_task + detect_paragraph_result + detect_sentence_result 三表
    private final Map<Long, Map<String, Object>> tasks = new ConcurrentHashMap<>();
    private final AtomicLong idGen = new AtomicLong(1000);

    private String inferenceBase() {
        return "http://" + inferenceHost + ":" + inferencePort;
    }

    private static final Map<String, Integer> THRESHOLD = Map.of(
            "BACHELOR", 20, "MASTER", 15, "PHD", 10
    );

    /* ==================== §3.1 提交论文 ==================== */

    @PostMapping("/detect/submit")
    public R<Map<String, Object>> submit(
            @RequestParam("file") MultipartFile file,
            @RequestParam("degreeType") String degreeType,
            @RequestParam(value = "title", required = false) String title) {
        if (file == null || file.isEmpty()) return R.fail(3002, "未能从文件中提取到有效文本");
        if (file.getSize() > 20L * 1024 * 1024) return R.fail(3001, "文件超过 20MB 限制");

        long id = idGen.incrementAndGet();
        String paperTitle = (title != null && !title.isBlank())
                ? title
                : file.getOriginalFilename();

        Map<String, Object> task = new HashMap<>();
        task.put("id", id);
        task.put("paperTitle", paperTitle);
        task.put("status", "PENDING");
        task.put("aiRate", null);
        task.put("degreeType", degreeType);
        task.put("threshold", THRESHOLD.getOrDefault(degreeType, 20));
        task.put("createdAt", LocalDateTime.now().toString());
        task.put("finishedAt", null);
        task.put("modelVersion", "stub-v0");
        tasks.put(id, task);

        // Phase 0：立即模拟完成，避免前端一直轮询空
        // 生产：投消息队列，异步走 Python 推理 → 融合 → 落库
        completeMock(id);

        Map<String, Object> resp = new HashMap<>();
        resp.put("taskId", id);
        resp.put("paperTitle", paperTitle);
        resp.put("status", task.get("status"));
        resp.put("createdAt", task.get("createdAt"));
        return R.ok(resp);
    }

    /* ==================== §3.2 列表 ==================== */

    @GetMapping("/detect/tasks")
    public R<Map<String, Object>> list(
            @RequestParam(value = "pageNum", defaultValue = "1") int pageNum,
            @RequestParam(value = "pageSize", defaultValue = "20") int pageSize,
            @RequestParam(value = "status", required = false) String status,
            @RequestParam(value = "keyword", required = false) String keyword) {

        List<Map<String, Object>> all = new ArrayList<>(tasks.values());
        all.sort(Comparator.comparing((Map<String, Object> m) -> (String) m.get("createdAt")).reversed());

        List<Map<String, Object>> filtered = all.stream()
                .filter(t -> status == null || status.isBlank() || status.equals(t.get("status")))
                .filter(t -> keyword == null || keyword.isBlank()
                        || ((String) t.get("paperTitle")).toLowerCase().contains(keyword.toLowerCase()))
                .toList();

        int from = Math.min((pageNum - 1) * pageSize, filtered.size());
        int to = Math.min(from + pageSize, filtered.size());

        Map<String, Object> resp = new HashMap<>();
        resp.put("total", filtered.size());
        resp.put("rows", filtered.subList(from, to));
        return R.ok(resp);
    }

    /* ==================== §3.3 详情 ==================== */

    @GetMapping("/detect/tasks/{id}")
    public R<Map<String, Object>> detail(@PathVariable long id) {
        Map<String, Object> task = tasks.get(id);
        if (task == null) return R.fail(3003, "任务不存在");
        return R.ok(task);
    }

    /* ==================== §3.4 重试 ==================== */

    @PostMapping("/detect/tasks/{id}/retry")
    public R<Map<String, Object>> retry(@PathVariable long id) {
        Map<String, Object> task = tasks.get(id);
        if (task == null) return R.fail(3003, "任务不存在");
        task.put("status", "PENDING");
        task.put("finishedAt", null);
        completeMock(id);
        return R.ok(task);
    }

    /* ==================== §3.5 取消 ==================== */

    @PostMapping("/detect/tasks/{id}/cancel")
    public R<Void> cancel(@PathVariable long id) {
        Map<String, Object> task = tasks.get(id);
        if (task == null) return R.fail(3003, "任务不存在");
        task.put("status", "FAILED");
        return R.ok();
    }

    /* ==================== §3.6 删除 ==================== */

    @DeleteMapping("/detect/tasks/{id}")
    public R<Void> delete(@PathVariable long id) {
        tasks.remove(id);
        return R.ok();
    }

    /* ==================== §4 降 AIGC ==================== */

    @PostMapping("/humanize")
    public R<Map<String, Object>> humanize(@RequestBody Map<String, Object> body) {
        Object taskIdObj = body.get("taskId");
        Object paragraphIdxObj = body.get("paragraphIdx");
        Long taskId = taskIdObj == null ? null : ((Number) taskIdObj).longValue();
        Integer paragraphIdx = paragraphIdxObj == null ? null : ((Number) paragraphIdxObj).intValue();

        String original = "";
        if (taskId != null && paragraphIdx != null) {
            Map<String, Object> task = tasks.get(taskId);
            if (task != null) {
                @SuppressWarnings("unchecked")
                List<Map<String, Object>> paragraphs = (List<Map<String, Object>>) task.get("paragraphs");
                if (paragraphs != null && paragraphIdx < paragraphs.size()) {
                    original = (String) paragraphs.get(paragraphIdx).get("text");
                }
            }
        }
        if (original.isEmpty()) original = (String) body.getOrDefault("text", "");

        try {
            String reqJson = objectMapper.writeValueAsString(Map.of(
                    "text", original,
                    "style", body.getOrDefault("style", "academic")
            ));
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(inferenceBase() + "/api/v1/humanize"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(reqJson))
                    .build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            Map<String, Object> py = objectMapper.readValue(response.body(), Map.class);

            Map<String, Object> resp = new HashMap<>();
            resp.put("humanizeTaskId", idGen.incrementAndGet());
            resp.put("originalText", original);
            resp.put("rewrittenText", py.get("rewritten_text"));
            resp.put("qualityScore", py.get("quality_score"));
            resp.put("modelVersion", py.get("model_version"));
            return R.ok(resp);
        } catch (Exception e) {
            log.error("humanize failed", e);
            return R.fail(5000, "改写服务暂时不可用");
        }
    }

    /* ==================== §8.2 单段检测（内部/直调，非契约主接口） ==================== */

    @PostMapping("/detect/paragraph")
    public R<Map<String, Object>> detectParagraph(@RequestBody Map<String, Object> body) {
        try {
            String reqJson = objectMapper.writeValueAsString(Map.of(
                    "text", body.getOrDefault("text", ""),
                    "return_calibrated", true,
                    "return_sentences", Boolean.TRUE.equals(body.get("returnSentences"))
            ));
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(inferenceBase() + "/api/v1/detect/paragraph"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(reqJson))
                    .build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            return R.ok(objectMapper.readValue(response.body(), Map.class));
        } catch (Exception e) {
            log.error("detect paragraph failed", e);
            return R.fail(5000, "检测服务暂时不可用，请稍后重试");
        }
    }

    /* ==================== 运维 ==================== */

    @GetMapping("/detect/health")
    public R<Map<String, Object>> health() {
        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(inferenceBase() + "/health"))
                    .GET().build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            return R.ok(objectMapper.readValue(response.body(), Map.class));
        } catch (Exception e) {
            return R.fail(5000, "推理服务不可用");
        }
    }

    /* ==================== 内部：mock 完成任务 ==================== */

    /**
     * 提交后立即调 Python stub 生成假报告，模拟异步完成
     * 生产：改为投 MQ + Celery/线程池异步走真实融合流水
     */
    private void completeMock(long id) {
        Map<String, Object> task = tasks.get(id);
        if (task == null) return;

        List<Map<String, Object>> paragraphs = new ArrayList<>();
        String[] samples = {
                "随着人工智能技术的快速发展，深度学习在自然语言处理领域的应用日益广泛。值得注意的是，情感分析作为其中的重要分支，已经成为学术界和工业界共同关注的焦点。",
                "我们在实验中发现，当训练数据里混入大量口语化评论时，模型在正式文本上的表现反而下降了两个点，这个现象起初让我们很困惑。"
        };
        double sumRate = 0;
        for (int i = 0; i < samples.length; i++) {
            try {
                String reqJson = objectMapper.writeValueAsString(Map.of(
                        "text", samples[i],
                        "return_calibrated", true,
                        "return_sentences", true
                ));
                HttpRequest request = HttpRequest.newBuilder()
                        .uri(URI.create(inferenceBase() + "/api/v1/detect/paragraph"))
                        .header("Content-Type", "application/json")
                        .POST(HttpRequest.BodyPublishers.ofString(reqJson))
                        .build();
                HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
                Map<String, Object> py = objectMapper.readValue(response.body(), Map.class);

                Map<String, Object> para = new HashMap<>();
                para.put("paragraphIdx", i);
                para.put("text", samples[i]);
                para.put("aiProb", py.get("ai_prob"));
                para.put("calibratedProb", py.get("calibrated_prob"));
                para.put("confidenceInterval", py.get("interval"));
                para.put("sourceLabel", i == 0 ? "qwen" : "human");
                para.put("warnings", List.of());

                // 转换 sentences 字段名 snake→camel
                @SuppressWarnings("unchecked")
                List<Map<String, Object>> pySents = (List<Map<String, Object>>) py.get("sentences");
                List<Map<String, Object>> sentences = new ArrayList<>();
                if (pySents != null) {
                    for (Map<String, Object> s : pySents) {
                        sentences.add(Map.of(
                                "sentenceIdx", s.get("sentence_idx"),
                                "text", samples[i].substring(
                                        ((Number) s.get("offset_start")).intValue(),
                                        Math.min(((Number) s.get("offset_end")).intValue(), samples[i].length())
                                ),
                                "aiProb", s.get("ai_prob")
                        ));
                    }
                }
                para.put("sentences", sentences);
                paragraphs.add(para);

                sumRate += ((Number) py.get("calibrated_prob")).doubleValue() * 100;
            } catch (Exception e) {
                log.warn("stub inference failed for paragraph {}", i, e);
            }
        }

        task.put("paragraphs", paragraphs);
        task.put("sourceLabels", Map.of("qwen", 0.42, "gpt", 0.31, "human", 0.27));
        task.put("aiRate", Math.round(sumRate / Math.max(paragraphs.size(), 1) * 10) / 10.0);
        task.put("status", "DONE");
        task.put("finishedAt", LocalDateTime.now().toString());
    }
}
