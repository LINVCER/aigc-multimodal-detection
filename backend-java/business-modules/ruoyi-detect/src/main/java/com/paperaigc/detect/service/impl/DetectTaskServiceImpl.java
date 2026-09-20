package com.paperaigc.detect.service.impl;

import com.paperaigc.detect.common.constant.DetectConstants;
import com.paperaigc.detect.common.constant.ScenarioConstants;
import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import com.paperaigc.detect.common.util.ParamUtils;
import com.paperaigc.detect.domain.dto.DetectTaskQueryDTO;
import com.paperaigc.detect.domain.dto.HumanizeDTO;
import com.paperaigc.detect.domain.entity.AudioSegmentResult;
import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.entity.ImageSegmentResult;
import com.paperaigc.detect.domain.entity.ParagraphResult;
import com.paperaigc.detect.domain.entity.SentenceResult;
import com.paperaigc.detect.domain.vo.DetectTaskDetailVO;
import com.paperaigc.detect.domain.vo.DetectTaskVO;
import com.paperaigc.detect.domain.vo.PageVO;
import com.paperaigc.detect.domain.vo.StatisticsVO;
import com.paperaigc.detect.repository.IDetectTaskRepository;
import com.paperaigc.detect.service.IDetectTaskService;
import com.paperaigc.detect.service.IInferenceClient;
import com.paperaigc.detect.service.IStorageService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.YearMonth;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 检测任务业务实现
 *
 * <p>Phase 0：submit 后同步调 IInferenceClient 完成推理，立即返回 DONE 任务。
 * Phase B 起改为投消息队列 + 异步 Worker 走真实推理管线。</p>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DetectTaskServiceImpl implements IDetectTaskService {

    private final IDetectTaskRepository taskRepository;
    private final IInferenceClient inferenceClient;
    private final IStorageService storageService;
    private final TextProcessor textProcessor;
    private final com.paperaigc.detect.service.IScenarioThresholdService scenarioThresholdService;

    /* ==================== §3.1 提交 ==================== */

    @Override
    @Transactional(rollbackFor = Exception.class)
    public DetectTask submit(MultipartFile file, String scenario, String degreeType, String title,
                             Long userId, String modality) {
        if (file == null || file.isEmpty()) throw new BizException(ErrorCode.DETECT_EXTRACT_FAILED, "未上传文件");

        // 归一模态：客户端指定优先；否则按后缀猜
        String mod = ParamUtils.isBlank(modality)
                ? DetectConstants.guessModality(file.getOriginalFilename())
                : modality;
        if (!DetectConstants.MODALITIES.contains(mod)) {
            throw new BizException(ErrorCode.PARAM_INVALID, "unknown modality: " + mod);
        }

        return switch (mod) {
            case DetectConstants.MODALITY_AUDIO -> submitAudio(file, scenario, title, userId);
            case DetectConstants.MODALITY_IMAGE -> submitImage(file, scenario, title, userId);
            default -> submitText(file, scenario, degreeType, title, userId);
        };
    }

    /* ==================== §3.1 文本模态 ==================== */

    private DetectTask submitText(MultipartFile file, String scenario, String degreeType, String title, Long userId) {
        // 基础校验
        if (file.getSize() > DetectConstants.FILE_SIZE_MAX) throw new BizException(ErrorCode.DETECT_FILE_TOO_LARGE);
        if (!textProcessor.isAllowedFormat(file)) throw new BizException(ErrorCode.DETECT_FORMAT_UNSUPPORT);

        // 场景归一
        String sc = ParamUtils.isBlank(scenario) ? ScenarioConstants.migrateDegreeType(degreeType) : scenario;

        // 抽文本 + 段落切分 + 非正文过滤
        String fullText = textProcessor.extractText(file);
        List<String> raw = textProcessor.splitParagraphs(fullText);
        List<Map<String, Object>> metas = textProcessor.filterNonBody(raw);
        long bodyCount = metas.stream().filter(m -> !Boolean.TRUE.equals(m.get("excluded"))).count();
        if (bodyCount == 0) {
            throw new BizException(ErrorCode.DETECT_EXTRACT_FAILED, "未识别到有效正文（扫描件、加密或仅参考文献）");
        }

        String paperTitle = (title != null && !title.isBlank()) ? title : file.getOriginalFilename();
        DetectTask task = DetectTask.builder()
                .userId(userId)
                .modality(DetectConstants.MODALITY_TEXT)
                .paperTitle(paperTitle)
                .status(DetectConstants.STATUS_PENDING)
                .scenario(sc)
                .threshold(scenarioThresholdService.threshold(sc))
                .modelVersion("stub-v0")
                .originalFilename(file.getOriginalFilename())
                .fileSize(file.getSize())
                .wordCount(metas.stream().mapToInt(m -> ((String) m.get("text")).length()).sum())
                .bodyParagraphCount(bodyCount)
                .excludedParagraphCount(metas.size() - (int) bodyCount)
                .createdAt(LocalDateTime.now())
                .build();
        task = taskRepository.save(task);

        try {
            task.setFilePath(storageService.save(file, task.getId()));
        } catch (Exception e) {
            log.warn("save uploaded file failed but continue task {}", task.getId(), e);
        }

        runInference(task, metas);
        taskRepository.update(task);
        return task;
    }

    /* ==================== §3.1 音频模态（Wave 5 · 骨架已就位；真模型待训练） ==================== */

    private DetectTask submitAudio(MultipartFile file, String scenario, String title, Long userId) {
        if (file.getSize() > DetectConstants.FILE_SIZE_MAX_AUDIO) {
            throw new BizException(ErrorCode.DETECT_FILE_TOO_LARGE, "音频超过 50MB");
        }
        // 简化校验：MIME 或后缀命中即放行（audio 白名单）
        String mime = file.getContentType();
        String name = file.getOriginalFilename();
        String ext = (name != null && name.lastIndexOf('.') >= 0)
                ? name.substring(name.lastIndexOf('.') + 1).toLowerCase() : "";
        boolean allowed = (mime != null && DetectConstants.ALLOWED_AUDIO_MIME.contains(mime))
                || DetectConstants.ALLOWED_AUDIO_EXT.contains(ext);
        if (!allowed) throw new BizException(ErrorCode.DETECT_FORMAT_UNSUPPORT, "音频格式不支持");

        // scenario 对音频语义弱化，但仍支持传入（默认 other）
        String sc = ParamUtils.isBlank(scenario) ? ScenarioConstants.OTHER : scenario;

        String paperTitle = (title != null && !title.isBlank()) ? title : name;
        DetectTask task = DetectTask.builder()
                .userId(userId)
                .modality(DetectConstants.MODALITY_AUDIO)
                .paperTitle(paperTitle)
                .status(DetectConstants.STATUS_PENDING)
                .scenario(sc)
                .threshold(scenarioThresholdService.threshold(sc))
                .modelVersion("audio-stub-v0")
                .originalFilename(name)
                .fileSize(file.getSize())
                .createdAt(LocalDateTime.now())
                .build();
        task = taskRepository.save(task);

        try {
            task.setFilePath(storageService.save(file, task.getId()));
        } catch (Exception e) {
            log.warn("save audio failed but continue task {}", task.getId(), e);
        }

        runAudioInference(task, file);
        taskRepository.update(task);
        return task;
    }

    @SuppressWarnings("unchecked")
    private void runAudioInference(DetectTask task, MultipartFile file) {
        try {
            byte[] bytes = file.getBytes();
            Map<String, Object> py = inferenceClient.detectAudio(bytes, file.getOriginalFilename(), true);

            Double cp = ParamUtils.toDouble(py.get("calibrated_prob"));
            Double durationSec = ParamUtils.toDouble(py.get("duration_sec"));
            List<Map<String, Object>> raw = (List<Map<String, Object>>) py.getOrDefault("segments", List.of());

            List<AudioSegmentResult> segments = new ArrayList<>(raw.size());
            for (int i = 0; i < raw.size(); i++) {
                Map<String, Object> s = raw.get(i);
                segments.add(AudioSegmentResult.builder()
                        .segmentIdx(ParamUtils.toInt(s.getOrDefault("segment_idx", i)))
                        .timeStart(ParamUtils.toDouble(s.get("time_start")))
                        .timeEnd(ParamUtils.toDouble(s.get("time_end")))
                        .aiProb(ParamUtils.toDouble(s.get("ai_prob")))
                        .calibratedProb(ParamUtils.toDouble(s.get("calibrated_prob")))
                        .sourceLabel((String) s.get("source_label"))
                        .waveformPeak(ParamUtils.toDouble(s.get("waveform_peak")))
                        .build());
            }

            task.setAudioSegments(segments);
            task.setAudioDurationSec(durationSec);
            task.setAiRate(cp == null ? null : Math.round(cp * 1000) / 10.0);   // → 百分制一位小数
            task.setStatus(DetectConstants.STATUS_DONE);
            task.setFinishedAt(LocalDateTime.now());
        } catch (Exception e) {
            log.error("audio inference failed for task {}", task.getId(), e);
            task.setStatus(DetectConstants.STATUS_FAILED);
            task.setFinishedAt(LocalDateTime.now());
        }
    }

    /* ==================== §3.1 图像模态（骨架已就位；Python 端点后补） ==================== */

    private DetectTask submitImage(MultipartFile file, String scenario, String title, Long userId) {
        if (file.getSize() > DetectConstants.FILE_SIZE_MAX_IMAGE) {
            throw new BizException(ErrorCode.DETECT_FILE_TOO_LARGE, "图片超过 20MB");
        }
        String mime = file.getContentType();
        String name = file.getOriginalFilename();
        String ext = (name != null && name.lastIndexOf('.') >= 0)
                ? name.substring(name.lastIndexOf('.') + 1).toLowerCase() : "";
        boolean allowed = (mime != null && DetectConstants.ALLOWED_IMAGE_MIME.contains(mime))
                || DetectConstants.ALLOWED_IMAGE_EXT.contains(ext);
        if (!allowed) throw new BizException(ErrorCode.DETECT_FORMAT_UNSUPPORT, "图片格式不支持");

        // scenario 对图像语义弱化，但仍支持传入（默认 other）
        String sc = ParamUtils.isBlank(scenario) ? ScenarioConstants.OTHER : scenario;

        String paperTitle = (title != null && !title.isBlank()) ? title : name;
        DetectTask task = DetectTask.builder()
                .userId(userId)
                .modality(DetectConstants.MODALITY_IMAGE)
                .paperTitle(paperTitle)
                .status(DetectConstants.STATUS_PENDING)
                .scenario(sc)
                .threshold(scenarioThresholdService.threshold(sc))
                .modelVersion("image-stub-v0")
                .originalFilename(name)
                .fileSize(file.getSize())
                .createdAt(LocalDateTime.now())
                .build();
        task = taskRepository.save(task);

        try {
            task.setFilePath(storageService.save(file, task.getId()));
        } catch (Exception e) {
            log.warn("save image failed but continue task {}", task.getId(), e);
        }

        runImageInference(task, file);
        taskRepository.update(task);
        return task;
    }

    @SuppressWarnings("unchecked")
    private void runImageInference(DetectTask task, MultipartFile file) {
        try {
            byte[] bytes = file.getBytes();
            Map<String, Object> py = inferenceClient.detectImage(bytes, file.getOriginalFilename(), true);
            fillImageResult(task, py);
        } catch (Exception e) {
            log.error("image inference failed for task {}", task.getId(), e);
            task.setStatus(DetectConstants.STATUS_FAILED);
            task.setFinishedAt(LocalDateTime.now());
        }
    }

    /**
     * runImageInference 的 bytes 版：retry 时从存储反读没有 MultipartFile，直接给字节流。
     */
    @SuppressWarnings("unchecked")
    private void runImageInferenceBytes(DetectTask task, byte[] bytes) {
        try {
            Map<String, Object> py = inferenceClient.detectImage(bytes, task.getOriginalFilename(), true);
            fillImageResult(task, py);
        } catch (Exception e) {
            log.error("image retry failed for task {}", task.getId(), e);
            task.setStatus(DetectConstants.STATUS_FAILED);
            task.setFinishedAt(LocalDateTime.now());
        }
    }

    @SuppressWarnings("unchecked")
    private void fillImageResult(DetectTask task, Map<String, Object> py) {
        Double cp = ParamUtils.toDouble(py.get("calibrated_prob"));
        List<Map<String, Object>> raw = (List<Map<String, Object>>) py.getOrDefault("regions", List.of());

        List<ImageSegmentResult> segs = new ArrayList<>(raw.size());
        for (int i = 0; i < raw.size(); i++) {
            Map<String, Object> r = raw.get(i);
            segs.add(ImageSegmentResult.builder()
                    .segmentIdx(ParamUtils.toInt(r.getOrDefault("segment_idx", i)))
                    .x(ParamUtils.toInt(r.get("x")))
                    .y(ParamUtils.toInt(r.get("y")))
                    .w(ParamUtils.toInt(r.get("w")))
                    .h(ParamUtils.toInt(r.get("h")))
                    .aiProb(ParamUtils.toDouble(r.get("ai_prob")))
                    .calibratedProb(ParamUtils.toDouble(r.get("calibrated_prob")))
                    .sourceLabel((String) r.get("source_label"))
                    .build());
        }

        task.setImageSegments(segs);
        task.setAiRate(cp == null ? null : Math.round(cp * 1000) / 10.0);   // → 百分制一位小数
        task.setStatus(DetectConstants.STATUS_DONE);
        task.setFinishedAt(LocalDateTime.now());
    }

    /**
     * 段落级推理 + 汇总 aiRate + 溯源
     */
    private void runInference(DetectTask task, List<Map<String, Object>> metas) {
        int limit = Math.min(metas.size(), 50);   // Phase 0 只标前 50 段控 latency
        List<ParagraphResult> paragraphs = new ArrayList<>();
        double sumRate = 0;
        int rateCount = 0;
        int attemptedCount = 0;   // 参与推理的段数（非 excluded）

        for (int i = 0; i < limit; i++) {
            Map<String, Object> meta = metas.get(i);
            String text = (String) meta.get("text");
            boolean excluded = Boolean.TRUE.equals(meta.get("excluded"));
            String sectionName = (String) meta.getOrDefault("sectionName", "正文");

            if (excluded) {
                paragraphs.add(ParagraphResult.builder()
                        .paragraphIdx(i).text(text)
                        .excluded(true).excludeReason((String) meta.get("excludeReason"))
                        .sectionName(sectionName).sentences(List.of()).build());
                continue;
            }

            attemptedCount++;
            try {
                Map<String, Object> py = inferenceClient.detectParagraph(text, true);
                double cp = ((Number) py.get("calibrated_prob")).doubleValue();
                paragraphs.add(ParagraphResult.builder()
                        .paragraphIdx(i).text(text).excluded(false)
                        .aiProb(ParamUtils.toDouble(py.get("ai_prob")))
                        .calibratedProb(cp)
                        .confidenceInterval(py.get("interval"))
                        .sourceLabel(cp >= 0.7 ? "qwen" : (cp >= 0.4 ? "gpt" : "human"))
                        .sectionName(sectionName)
                        .warnings(List.of())
                        .sentences(parseSentences(text, py))
                        .build());
                sumRate += cp * 100;
                rateCount++;
            } catch (Exception e) {
                log.warn("stub inference failed for paragraph {} of task {}", i, task.getId(), e);
            }
        }

        // ---------- 溯源汇总（只算正文段） ----------
        Map<String, Double> sourceLabels = new HashMap<>();
        long bodyTotal = paragraphs.stream().filter(p -> !p.isExcluded()).count();
        for (ParagraphResult p : paragraphs) {
            if (p.isExcluded()) continue;
            String label = p.getSourceLabel() == null ? "other" : p.getSourceLabel();
            sourceLabels.merge(label, 1.0, Double::sum);
        }
        sourceLabels.replaceAll((k, v) -> Math.round(v / Math.max(bodyTotal, 1) * 100) / 100.0);

        task.setParagraphs(paragraphs);
        task.setSourceLabels(sourceLabels);
        task.setAiRate(rateCount == 0 ? null : Math.round(sumRate / rateCount * 10) / 10.0);
        // 尝试了推理但一段都没成功 → 视为整体失败（避免展示"完成但无结果"）
        boolean allFailed = attemptedCount > 0 && rateCount == 0;
        task.setStatus(allFailed ? DetectConstants.STATUS_FAILED : DetectConstants.STATUS_DONE);
        task.setFinishedAt(LocalDateTime.now());
    }

    @SuppressWarnings("unchecked")
    private List<SentenceResult> parseSentences(String paraText, Map<String, Object> py) {
        List<Map<String, Object>> raw = (List<Map<String, Object>>) py.get("sentences");
        if (raw == null) return List.of();
        List<SentenceResult> out = new ArrayList<>(raw.size());
        for (Map<String, Object> s : raw) {
            int start = ((Number) s.get("offset_start")).intValue();
            int end = Math.min(((Number) s.get("offset_end")).intValue(), paraText.length());
            out.add(SentenceResult.builder()
                    .sentenceIdx(ParamUtils.toInt(s.get("sentence_idx")))
                    .text(paraText.substring(Math.max(0, start), Math.max(start, end)))
                    .aiProb(ParamUtils.toDouble(s.get("ai_prob")))
                    .build());
        }
        return out;
    }

    /* ==================== §3.2 列表 ==================== */

    @Override
    public PageVO<DetectTaskVO> page(DetectTaskQueryDTO q) {
        List<DetectTask> all = taskRepository.findAll().stream()
                .filter(t -> ParamUtils.isBlank(q.getStatus())   || q.getStatus().equals(t.getStatus()))
                .filter(t -> ParamUtils.isBlank(q.getScenario()) || q.getScenario().equals(t.getScenario()))
                .filter(t -> q.getUserId() == null || q.getUserId().equals(t.getUserId()))
                .filter(t -> ParamUtils.isBlank(q.getKeyword())
                        || ParamUtils.containsIgnoreCase(t.getPaperTitle(), q.getKeyword()))
                .filter(t -> q.getMinAiRate() == null || (t.getAiRate() != null && t.getAiRate() >= q.getMinAiRate()))
                .filter(t -> q.getMaxAiRate() == null || (t.getAiRate() != null && t.getAiRate() <= q.getMaxAiRate()))
                .sorted(Comparator.comparing(DetectTask::getCreatedAt,
                        Comparator.nullsLast(Comparator.reverseOrder())))
                .toList();

        int total = all.size();
        int pageNum = q.getPageNum() == null || q.getPageNum() < 1 ? 1 : q.getPageNum();
        int pageSize = q.getPageSize() == null || q.getPageSize() < 1 ? 20 : q.getPageSize();
        int from = Math.max(0, (pageNum - 1) * pageSize);
        int to = Math.min(total, from + pageSize);
        List<DetectTaskVO> rows = from >= total ? List.of()
                : all.subList(from, to).stream().map(DetectTaskVO::from).toList();
        return PageVO.of(total, rows);
    }

    /* ==================== §3.3 详情 ==================== */

    @Override
    public DetectTaskDetailVO detail(Long id) {
        return DetectTaskDetailVO.from(taskRepository.findById(id)
                .orElseThrow(() -> new BizException(ErrorCode.DETECT_TASK_NOT_FOUND)));
    }

    /* ==================== §3.4 重试 ==================== */

    @Override
    @Transactional(rollbackFor = Exception.class)
    public DetectTask retry(Long id) {
        DetectTask task = taskRepository.findById(id)
                .orElseThrow(() -> new BizException(ErrorCode.DETECT_TASK_NOT_FOUND));

        task.setStatus(DetectConstants.STATUS_PENDING);
        task.setFinishedAt(null);
        task.setAiRate(null);
        task.setParagraphs(null);
        task.setAudioSegments(null);
        task.setImageSegments(null);
        task.setSourceLabels(null);

        if (task.getFilePath() == null || !storageService.exists(task.getFilePath())) {
            log.warn("retry task {} but filePath missing/gone: {}", id, task.getFilePath());
            task.setStatus(DetectConstants.STATUS_FAILED);
            taskRepository.update(task);
            return task;
        }

        String mod = task.getModality() == null ? DetectConstants.MODALITY_TEXT : task.getModality();
        try {
            if (DetectConstants.MODALITY_AUDIO.equals(mod)) {
                byte[] bytes;
                try (java.io.InputStream is = storageService.read(task.getFilePath())) {
                    bytes = is.readAllBytes();
                }
                runAudioInferenceBytes(task, bytes);
            } else if (DetectConstants.MODALITY_IMAGE.equals(mod)) {
                byte[] bytes;
                try (java.io.InputStream is = storageService.read(task.getFilePath())) {
                    bytes = is.readAllBytes();
                }
                runImageInferenceBytes(task, bytes);
            } else {
                try (java.io.InputStream is = storageService.read(task.getFilePath())) {
                    String fullText = textProcessor.extractText(is, task.getOriginalFilename());
                    List<String> raw = textProcessor.splitParagraphs(fullText);
                    List<Map<String, Object>> metas = textProcessor.filterNonBody(raw);
                    runInference(task, metas);
                }
            }
        } catch (BizException e) {
            task.setStatus(DetectConstants.STATUS_FAILED);
            log.warn("retry task {} failed: {}", id, e.getMessage());
        } catch (Exception e) {
            task.setStatus(DetectConstants.STATUS_FAILED);
            log.error("retry task {} unexpected error", id, e);
        }

        taskRepository.update(task);
        return task;
    }

    /**
     * runAudioInference 的 bytes 版：retry 时从存储反读没有 MultipartFile，直接给字节流。
     */
    @SuppressWarnings("unchecked")
    private void runAudioInferenceBytes(DetectTask task, byte[] bytes) {
        try {
            Map<String, Object> py = inferenceClient.detectAudio(bytes, task.getOriginalFilename(), true);
            Double cp = ParamUtils.toDouble(py.get("calibrated_prob"));
            Double durationSec = ParamUtils.toDouble(py.get("duration_sec"));
            List<Map<String, Object>> raw = (List<Map<String, Object>>) py.getOrDefault("segments", List.of());

            List<AudioSegmentResult> segments = new ArrayList<>(raw.size());
            for (int i = 0; i < raw.size(); i++) {
                Map<String, Object> s = raw.get(i);
                segments.add(AudioSegmentResult.builder()
                        .segmentIdx(ParamUtils.toInt(s.getOrDefault("segment_idx", i)))
                        .timeStart(ParamUtils.toDouble(s.get("time_start")))
                        .timeEnd(ParamUtils.toDouble(s.get("time_end")))
                        .aiProb(ParamUtils.toDouble(s.get("ai_prob")))
                        .calibratedProb(ParamUtils.toDouble(s.get("calibrated_prob")))
                        .sourceLabel((String) s.get("source_label"))
                        .waveformPeak(ParamUtils.toDouble(s.get("waveform_peak")))
                        .build());
            }

            task.setAudioSegments(segments);
            task.setAudioDurationSec(durationSec);
            task.setAiRate(cp == null ? null : Math.round(cp * 1000) / 10.0);
            task.setStatus(DetectConstants.STATUS_DONE);
            task.setFinishedAt(LocalDateTime.now());
        } catch (Exception e) {
            log.error("audio retry failed for task {}", task.getId(), e);
            task.setStatus(DetectConstants.STATUS_FAILED);
            task.setFinishedAt(LocalDateTime.now());
        }
    }

    /* ==================== §3.5 取消 ==================== */

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void cancel(Long id) {
        DetectTask task = taskRepository.findById(id)
                .orElseThrow(() -> new BizException(ErrorCode.DETECT_TASK_NOT_FOUND));
        task.setStatus(DetectConstants.STATUS_FAILED);
        taskRepository.update(task);
    }

    /* ==================== §3.6 删除 ==================== */

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void delete(Long id) {
        taskRepository.findById(id).ifPresent(t -> {
            if (t.getFilePath() != null) storageService.delete(t.getFilePath());
            taskRepository.deleteById(id);
        });
    }

    /* ==================== §3.7 C 端统计 ==================== */

    @Override
    public StatisticsVO statistics() {
        LocalDate today = LocalDate.now();
        YearMonth thisMonth = YearMonth.from(today);
        int windowDays = 30;
        LocalDate startDate = today.minusDays(windowDays - 1L);

        int todayCount = 0, monthCount = 0, totalCount = 0, doneCount = 0, passCount = 0;
        double sumRate = 0;
        int rateCount = 0;
        int[] dailyCount = new int[windowDays];
        double[] dailyRateSum = new double[windowDays];
        int[] dailyRateN = new int[windowDays];

        for (DetectTask t : taskRepository.findAll()) {
            totalCount++;
            LocalDate d = t.getCreatedAt() == null ? null : t.getCreatedAt().toLocalDate();
            if (d == null) continue;

            if (d.equals(today)) todayCount++;
            if (YearMonth.from(d).equals(thisMonth)) monthCount++;

            if (DetectConstants.STATUS_DONE.equals(t.getStatus())) {
                doneCount++;
                Double aiRate = t.getAiRate();
                Integer threshold = t.getThreshold();
                if (aiRate != null) {
                    sumRate += aiRate;
                    rateCount++;
                    if (threshold != null && aiRate <= threshold) passCount++;
                }
            }
            if (!d.isBefore(startDate) && !d.isAfter(today)) {
                int idx = (int) ChronoUnit.DAYS.between(startDate, d);
                dailyCount[idx]++;
                if (t.getAiRate() != null) {
                    dailyRateSum[idx] += t.getAiRate();
                    dailyRateN[idx]++;
                }
            }
        }

        List<StatisticsVO.DailyTrendRow> trend = new ArrayList<>(windowDays);
        for (int i = 0; i < windowDays; i++) {
            trend.add(StatisticsVO.DailyTrendRow.builder()
                    .date(startDate.plusDays(i).toString())
                    .count(dailyCount[i])
                    .avgRate(dailyRateN[i] == 0 ? null
                            : Math.round(dailyRateSum[i] / dailyRateN[i] * 10) / 10.0)
                    .build());
        }

        return StatisticsVO.builder()
                .today(todayCount)
                .thisMonth(monthCount)
                .total(totalCount)
                .done(doneCount)
                .avgAiRate(rateCount == 0 ? null : Math.round(sumRate / rateCount * 10) / 10.0)
                .passRate(doneCount == 0 ? null : Math.round((double) passCount / doneCount * 1000) / 10.0)
                .dailyTrend(trend)
                .build();
    }

    /* ==================== §4 降 AIGC ==================== */

    @Override
    public Map<String, Object> humanize(HumanizeDTO dto) {
        String original = "";
        if (dto.getTaskId() != null && dto.getParagraphIdx() != null) {
            DetectTask task = taskRepository.findById(dto.getTaskId()).orElse(null);
            if (task != null && task.getParagraphs() != null && dto.getParagraphIdx() < task.getParagraphs().size()) {
                original = task.getParagraphs().get(dto.getParagraphIdx()).getText();
            }
        }
        if (original == null || original.isEmpty()) {
            original = dto.getText() == null ? "" : dto.getText();
        }

        Map<String, Object> py = inferenceClient.humanize(original, dto.getStyle());
        Map<String, Object> resp = new HashMap<>();
        resp.put("originalText", original);
        resp.put("rewrittenText", py.get("rewritten_text"));
        resp.put("qualityScore", py.get("quality_score"));
        resp.put("modelVersion", py.get("model_version"));
        return resp;
    }

    /* ==================== §8.2 单段直接检测 ==================== */

    @Override
    public Map<String, Object> detectParagraph(String text, boolean returnSentences) {
        return inferenceClient.detectParagraph(text, returnSentences);
    }

    /* ==================== 推理健康 ==================== */

    @Override
    public Map<String, Object> inferenceHealth() {
        return inferenceClient.health();
    }
}
