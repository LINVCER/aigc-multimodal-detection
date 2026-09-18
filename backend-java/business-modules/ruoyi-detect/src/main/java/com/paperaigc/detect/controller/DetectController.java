package com.paperaigc.detect.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.tika.Tika;
import org.apache.tika.exception.TikaException;
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

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
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
    /** Tika 线程安全，可长期复用 */
    private final Tika tika = new Tika();

    // 内存态：任务表；生产替换为 detect_task + detect_paragraph_result + detect_sentence_result 三表
    private final Map<Long, Map<String, Object>> tasks = new ConcurrentHashMap<>();
    /** 任务 → 抽出的段落原文列表，供 completeMock 用真实文本调 Python */
    private final Map<Long, List<String>> taskParagraphs = new ConcurrentHashMap<>();
    private final AtomicLong idGen = new AtomicLong(1000);

    private String inferenceBase() {
        return "http://" + inferenceHost + ":" + inferencePort;
    }

    private static final Map<String, Integer> THRESHOLD = Map.of(
            "BACHELOR", 20, "MASTER", 15, "PHD", 10
    );

    /** 支持的 MIME 白名单 */
    private static final Set<String> ALLOWED_MIME = new HashSet<>(Arrays.asList(
            "application/pdf",
            "application/msword",                                                         // .doc
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",    // .docx
            "text/plain",
            "application/octet-stream"                                                    // 小程序上传常报此 MIME，靠后缀名再兜一次
    ));

    /** 支持的后缀白名单（MIME 不可靠时兜底） */
    private static final Set<String> ALLOWED_EXT = new HashSet<>(Arrays.asList(
            "pdf", "doc", "docx", "txt"
    ));

    /* ==================== §3.1 提交论文 ==================== */

    @PostMapping("/detect/submit")
    public R<Map<String, Object>> submit(
            @RequestParam("file") MultipartFile file,
            @RequestParam("degreeType") String degreeType,
            @RequestParam(value = "title", required = false) String title) {
        if (file == null || file.isEmpty()) return R.fail(3002, "未能从文件中提取到有效文本");
        if (file.getSize() > 20L * 1024 * 1024) return R.fail(3001, "文件超过 20MB 限制");

        // MIME + 后缀双重校验，防止非文档文件
        if (!isAllowedFormat(file)) {
            return R.fail(3000, "论文格式不支持，请上传 PDF / DOC / DOCX / TXT");
        }

        // Tika 抽真实文本 → 切段
        List<String> paragraphs;
        try {
            String fullText = extractText(file);
            paragraphs = splitParagraphs(fullText);
        } catch (Exception e) {
            log.error("extract text failed: {}", file.getOriginalFilename(), e);
            return R.fail(3002, "文档解析失败：" + e.getMessage());
        }
        if (paragraphs.isEmpty()) {
            return R.fail(3002, "未能从文件中提取到有效文本（可能是扫描件或加密文档）");
        }

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
        task.put("wordCount", paragraphs.stream().mapToInt(String::length).sum());
        tasks.put(id, task);
        taskParagraphs.put(id, paragraphs);

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

    /* ==================== 文件格式识别 + Tika 抽文本 ==================== */

    /**
     * MIME 白名单 + 后缀名兜底（小程序上传常 MIME 为 octet-stream）
     */
    private boolean isAllowedFormat(MultipartFile file) {
        String mime = file.getContentType();
        String name = file.getOriginalFilename();
        String ext = "";
        if (name != null) {
            int dot = name.lastIndexOf('.');
            if (dot >= 0 && dot < name.length() - 1) {
                ext = name.substring(dot + 1).toLowerCase();
            }
        }
        boolean mimeOk = mime != null && ALLOWED_MIME.contains(mime);
        boolean extOk = ALLOWED_EXT.contains(ext);
        // 至少一方通过（防浏览器 MIME 报错 + 防重命名冒充）
        return mimeOk || extOk;
    }

    /**
     * 用 Apache Tika 抽文本，一网打尽 PDF / DOC / DOCX / TXT / RTF / ODT 等
     */
    private String extractText(MultipartFile file) throws IOException, TikaException {
        try (InputStream is = file.getInputStream()) {
            // parseToString 默认最大 100KB 文本；论文可能大，放到 1MB
            return tika.parseToString(is, new org.apache.tika.metadata.Metadata(), 1_000_000);
        }
    }

    /**
     * 段落切分：优先按空行分（PDF / DOCX 段间常有），过短段合并到下一段，过长段按标点切
     */
    private List<String> splitParagraphs(String text) {
        List<String> out = new ArrayList<>();
        if (text == null || text.isBlank()) return out;

        // 归一化换行 + 去连续空行
        String norm = text.replace("\r\n", "\n").replace("\r", "\n");

        StringBuilder buf = new StringBuilder();
        for (String raw : norm.split("\n\\s*\n")) {
            String p = raw.replaceAll("[\\t ]+", " ").trim();
            if (p.isEmpty()) continue;

            // 过短段（<30 字）先攒着，避免"标题""图注"单独成段
            if (p.length() < 30) {
                if (buf.length() > 0) buf.append(' ');
                buf.append(p);
                if (buf.length() >= 30) {
                    out.add(buf.toString());
                    buf.setLength(0);
                }
                continue;
            }

            if (buf.length() > 0) {
                out.add(buf + " " + p);
                buf.setLength(0);
            } else {
                out.add(p);
            }
        }
        if (buf.length() > 0) out.add(buf.toString());

        // 过长段（>800 字）按句号/问号/感叹号切
        List<String> normalized = new ArrayList<>();
        for (String p : out) {
            if (p.length() <= 800) {
                normalized.add(p);
                continue;
            }
            StringBuilder chunk = new StringBuilder();
            for (int i = 0; i < p.length(); i++) {
                chunk.append(p.charAt(i));
                char c = p.charAt(i);
                boolean isEnd = c == '。' || c == '！' || c == '？' || c == '.' || c == '!' || c == '?';
                if (isEnd && chunk.length() >= 400) {
                    normalized.add(chunk.toString().trim());
                    chunk.setLength(0);
                }
            }
            if (chunk.length() > 0) normalized.add(chunk.toString().trim());
        }
        return normalized;
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
     * 提交后立即用 Tika 抽出的真实段落调 Python stub，生成检测报告，模拟异步完成。
     * 生产：改为投 MQ + Celery/线程池异步走真实融合流水（+ 段落级校准、Arbitrator 仲裁）。
     */
    private void completeMock(long id) {
        Map<String, Object> task = tasks.get(id);
        if (task == null) return;

        // 从 taskParagraphs 拿抽出的真实段落；兜底 fallback 保留可跑通
        List<String> texts = taskParagraphs.getOrDefault(id, List.of(
                "随着人工智能技术的快速发展，深度学习在自然语言处理领域的应用日益广泛。值得注意的是，情感分析作为其中的重要分支，已经成为学术界和工业界共同关注的焦点。",
                "我们在实验中发现，当训练数据里混入大量口语化评论时，模型在正式文本上的表现反而下降了两个点，这个现象起初让我们很困惑。"
        ));

        // 大论文只标注前 50 段以控 Phase 0 latency（生产走异步全量）
        int limit = Math.min(texts.size(), 50);

        List<Map<String, Object>> paragraphs = new ArrayList<>();
        double sumRate = 0;
        int rateCount = 0;

        for (int i = 0; i < limit; i++) {
            String text = texts.get(i);
            try {
                String reqJson = objectMapper.writeValueAsString(Map.of(
                        "text", text,
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
                para.put("text", text);
                para.put("aiProb", py.get("ai_prob"));
                para.put("calibratedProb", py.get("calibrated_prob"));
                para.put("confidenceInterval", py.get("interval"));
                // sourceLabel：真实场景走 §8.2 attribute 接口；stub 期用 calibratedProb 简单映射
                double cp = ((Number) py.get("calibrated_prob")).doubleValue();
                para.put("sourceLabel", cp >= 0.7 ? "qwen" : (cp >= 0.4 ? "gpt" : "human"));
                para.put("warnings", List.of());

                // sentences 字段 snake→camel + 用真实段落文本切片
                @SuppressWarnings("unchecked")
                List<Map<String, Object>> pySents = (List<Map<String, Object>>) py.get("sentences");
                List<Map<String, Object>> sentences = new ArrayList<>();
                if (pySents != null) {
                    for (Map<String, Object> s : pySents) {
                        int start = ((Number) s.get("offset_start")).intValue();
                        int end = Math.min(((Number) s.get("offset_end")).intValue(), text.length());
                        sentences.add(Map.of(
                                "sentenceIdx", s.get("sentence_idx"),
                                "text", text.substring(Math.max(0, start), Math.max(start, end)),
                                "aiProb", s.get("ai_prob")
                        ));
                    }
                }
                para.put("sentences", sentences);
                paragraphs.add(para);

                sumRate += cp * 100;
                rateCount++;
            } catch (Exception e) {
                log.warn("stub inference failed for paragraph {} of task {}", i, id, e);
            }
        }

        // 溯源汇总：按 sourceLabel 计数占比（生产替换为真实 attribute 融合）
        Map<String, Double> sourceLabels = new HashMap<>();
        int total = paragraphs.size();
        for (Map<String, Object> p : paragraphs) {
            String label = (String) p.getOrDefault("sourceLabel", "other");
            sourceLabels.merge(label, 1.0, Double::sum);
        }
        sourceLabels.replaceAll((k, v) -> Math.round(v / Math.max(total, 1) * 100) / 100.0);

        task.put("paragraphs", paragraphs);
        task.put("sourceLabels", sourceLabels);
        task.put("aiRate", rateCount == 0 ? null : Math.round(sumRate / rateCount * 10) / 10.0);
        task.put("status", "DONE");
        task.put("finishedAt", LocalDateTime.now().toString());

        // 释放段落原文（已落进 task.paragraphs，taskParagraphs 不再需要）
        taskParagraphs.remove(id);
    }
}
