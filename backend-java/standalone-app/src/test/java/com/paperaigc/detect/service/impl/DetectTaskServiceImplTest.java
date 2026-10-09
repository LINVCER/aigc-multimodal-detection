package com.paperaigc.detect.service.impl;

import com.paperaigc.detect.common.constant.DetectConstants;
import com.paperaigc.detect.common.constant.ScenarioConstants;
import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import com.paperaigc.detect.domain.dto.DetectTaskQueryDTO;
import com.paperaigc.detect.domain.dto.HumanizeDTO;
import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.vo.DetectTaskDetailVO;
import com.paperaigc.detect.domain.vo.DetectTaskVO;
import com.paperaigc.detect.domain.vo.PageVO;
import com.paperaigc.detect.domain.vo.StatisticsVO;
import com.paperaigc.detect.repository.IDetectTaskRepository;
import com.paperaigc.detect.service.IDetectAnalyticsService;
import com.paperaigc.detect.service.IInferenceClient;
import com.paperaigc.detect.service.INotifyService;
import com.paperaigc.detect.service.IReportCredentialService;
import com.paperaigc.detect.service.IScenarioThresholdService;
import com.paperaigc.detect.service.IStorageService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.web.multipart.MultipartFile;

import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.Executor;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 检测任务服务单元测试 —— submit / page / detail / retry / cancel / delete / statistics / humanize
 *
 * <p>协作组件全部 mock，聚焦 Service 自身的编排、状态流转与错误分支。</p>
 */
@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
@DisplayName("DetectTaskServiceImpl · 检测任务服务")
class DetectTaskServiceImplTest {

    @Mock private IDetectTaskRepository taskRepository;
    @Mock private IInferenceClient inferenceClient;
    @Mock private IStorageService storageService;
    @Mock private TextProcessor textProcessor;
    @Mock private IScenarioThresholdService scenarioThresholdService;
    @Mock private INotifyService notifyService;
    @Mock private IDetectAnalyticsService analyticsService;
    @Mock private IReportCredentialService credentialService;

    // 直接执行器：让提交后异步入队的推理在测试线程内同步跑完，submit 返回时已是终态，便于断言 DONE/FAILED
    private final Executor directExecutor = Runnable::run;

    private DetectTaskServiceImpl service;

    @BeforeEach
    void setUp() {
        service = new DetectTaskServiceImpl(taskRepository, inferenceClient, storageService,
                textProcessor, scenarioThresholdService, notifyService, analyticsService, credentialService,
                directExecutor);
    }

    /* ==================== §3.1 提交 ==================== */

    @Test
    @DisplayName("提交空文件 → DETECT_EXTRACT_FAILED")
    void submitEmptyFile() {
        MultipartFile empty = new MockMultipartFile("file", "a.txt", "text/plain", new byte[0]);
        assertThatThrownBy(() -> service.submit(empty, "academic_master", null, null, null, null, null))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode())
                .isEqualTo(ErrorCode.DETECT_EXTRACT_FAILED.getCode());
    }

    @Test
    @DisplayName("提交非法格式 → DETECT_FORMAT_UNSUPPORT")
    void submitUnsupportedFormat() {
        stubTextPipeline();
        when(textProcessor.isAllowedFormat(any())).thenReturn(false);

        assertThatThrownBy(() -> service.submit(txt("hello body"), "academic_master", null, null, null, null, null))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode())
                .isEqualTo(ErrorCode.DETECT_FORMAT_UNSUPPORT.getCode());
    }

    @Test
    @DisplayName("提交后无有效正文 → DETECT_EXTRACT_FAILED")
    void submitNoBody() {
        stubTextPipeline();
        when(textProcessor.isAllowedFormat(any())).thenReturn(true);
        when(textProcessor.filterNonBody(any())).thenReturn(List.of(
                meta("参考文献", true, "reference"),
                meta("[1] 张三. 论文[J]. 2024.", true, "reference")));

        assertThatThrownBy(() -> service.submit(txt("refs"), "academic_master", null, null, null, null, null))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode())
                .isEqualTo(ErrorCode.DETECT_EXTRACT_FAILED.getCode());
    }

    @Test
    @DisplayName("提交成功 → 状态 DONE、AI 率汇总、签发凭证、落库更新")
    void submitSuccess() {
        stubTextPipeline();
        when(textProcessor.isAllowedFormat(any())).thenReturn(true);
        when(textProcessor.filterNonBody(any())).thenReturn(List.of(
                meta("第一段正文内容用于检测，长度足够。", false, null),
                meta("第二段正文内容用于检测，长度足够。", false, null)));
        when(scenarioThresholdService.threshold("academic_master")).thenReturn(15);
        when(taskRepository.save(any())).thenAnswer(inv -> {
            DetectTask t = inv.getArgument(0);
            t.setId(100L);
            return t;
        });
        when(storageService.save(any(), anyLong())).thenReturn("storage/202610/100.txt");
        when(inferenceClient.detectParagraph(anyString(), eq(true))).thenReturn(pyResult(0.85));

        DetectTask task = service.submit(txt("body"), "academic_master", null, "我的论文", 7L, null, null);

        assertThat(task.getId()).isEqualTo(100L);
        assertThat(task.getStatus()).isEqualTo(DetectConstants.STATUS_DONE);
        assertThat(task.getScenario()).isEqualTo(ScenarioConstants.ACADEMIC_MASTER);
        assertThat(task.getThreshold()).isEqualTo(15);
        assertThat(task.getAiRate()).isEqualTo(85.0);
        assertThat(task.getBodyParagraphCount()).isEqualTo(2L);
        assertThat(task.getExcludedParagraphCount()).isZero();
        assertThat(task.getFilePath()).isEqualTo("storage/202610/100.txt");
        assertThat(task.getPaperTitle()).isEqualTo("我的论文");
        assertThat(task.getSourceLabels()).containsKey("qwen");
        verify(taskRepository, times(2)).update(task);
        verify(credentialService).ensure(task);
        verify(analyticsService).record(task);
        verify(notifyService).taskDone(task);
    }

    @Test
    @DisplayName("提交未传 scenario → 用旧字段 degreeType 迁移")
    void submitDegreeTypeFallback() {
        stubTextPipeline();
        when(textProcessor.isAllowedFormat(any())).thenReturn(true);
        when(textProcessor.filterNonBody(any())).thenReturn(List.of(meta("正文内容长度足够用于检测。", false, null)));
        when(taskRepository.save(any())).thenAnswer(inv -> {
            DetectTask t = inv.getArgument(0);
            t.setId(1L);
            return t;
        });
        when(inferenceClient.detectParagraph(anyString(), eq(true))).thenReturn(pyResult(0.5));

        DetectTask task = service.submit(txt("body"), null, "PHD", null, null, null, null);

        assertThat(task.getScenario()).isEqualTo(ScenarioConstants.ACADEMIC_PHD);
        verify(scenarioThresholdService).threshold(ScenarioConstants.ACADEMIC_PHD);
    }

    @Test
    @DisplayName("全部段落推理失败 → 状态 FAILED 且不发完成通知")
    void submitAllInferenceFailed() {
        stubTextPipeline();
        when(textProcessor.isAllowedFormat(any())).thenReturn(true);
        when(textProcessor.filterNonBody(any())).thenReturn(List.of(meta("正文内容长度足够用于检测。", false, null)));
        when(taskRepository.save(any())).thenAnswer(inv -> {
            DetectTask t = inv.getArgument(0);
            t.setId(2L);
            return t;
        });
        when(inferenceClient.detectParagraph(anyString(), eq(true)))
                .thenThrow(new RuntimeException("inference down"));

        DetectTask task = service.submit(txt("body"), "other", null, null, null, null, null);

        assertThat(task.getStatus()).isEqualTo(DetectConstants.STATUS_FAILED);
        verify(notifyService, never()).taskDone(any());
        verify(credentialService, never()).ensure(any());
    }

    /* ==================== §3.2 列表 ==================== */

    @Test
    @DisplayName("列表：状态 + 关键字过滤，按创建时间倒序分页")
    void pageFilterAndPaginate() {
        DetectTask a = task(1L, "深度学习检测研究", DetectConstants.STATUS_DONE, 20.0, LocalDateTime.of(2026, 10, 1, 10, 0));
        DetectTask b = task(2L, "自然语言处理综述", DetectConstants.STATUS_DONE, 40.0, LocalDateTime.of(2026, 10, 3, 10, 0));
        DetectTask c = task(3L, "图像分割方法", DetectConstants.STATUS_FAILED, null, LocalDateTime.of(2026, 10, 2, 10, 0));
        when(taskRepository.findAll()).thenReturn(List.of(a, b, c));

        DetectTaskQueryDTO q = new DetectTaskQueryDTO();
        q.setStatus(DetectConstants.STATUS_DONE);
        q.setPageNum(1);
        q.setPageSize(1);

        PageVO<DetectTaskVO> page = service.page(q);

        assertThat(page.getTotal()).isEqualTo(2);
        assertThat(page.getRows()).hasSize(1);
        assertThat(page.getRows().get(0).getId()).isEqualTo(2L);   // 最新在前
    }

    @Test
    @DisplayName("列表：关键字大小写不敏感 + AI 率区间过滤")
    void pageKeywordAndRateRange() {
        DetectTask a = task(1L, "Attention Is All You Need", DetectConstants.STATUS_DONE, 55.0, LocalDateTime.now());
        DetectTask b = task(2L, "卷积神经网络", DetectConstants.STATUS_DONE, 12.0, LocalDateTime.now());
        when(taskRepository.findAll()).thenReturn(List.of(a, b));

        DetectTaskQueryDTO q = new DetectTaskQueryDTO();
        q.setKeyword("attention");
        q.setMinAiRate(30.0);

        PageVO<DetectTaskVO> page = service.page(q);

        assertThat(page.getTotal()).isEqualTo(1);
        assertThat(page.getRows().get(0).getPaperTitle()).contains("Attention");
    }

    @Test
    @DisplayName("列表：页码越界返回空行但总数不变")
    void pageOutOfRange() {
        when(taskRepository.findAll()).thenReturn(List.of(
                task(1L, "A", DetectConstants.STATUS_DONE, 10.0, LocalDateTime.now())));
        DetectTaskQueryDTO q = new DetectTaskQueryDTO();
        q.setPageNum(5);
        q.setPageSize(20);

        PageVO<DetectTaskVO> page = service.page(q);

        assertThat(page.getTotal()).isEqualTo(1);
        assertThat(page.getRows()).isEmpty();
    }

    /* ==================== §3.3 详情 ==================== */

    @Test
    @DisplayName("详情：任务不存在 → DETECT_TASK_NOT_FOUND")
    void detailNotFound() {
        when(taskRepository.findById(9L)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> service.detail(9L))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode())
                .isEqualTo(ErrorCode.DETECT_TASK_NOT_FOUND.getCode());
    }

    @Test
    @DisplayName("详情：填充指纹 / 验证地址，并回填父任务对比信息")
    void detailFillsCredentialAndParent() {
        DetectTask parent = task(1L, "初稿", DetectConstants.STATUS_DONE, 30.0, LocalDateTime.of(2026, 9, 1, 9, 0));
        parent.setModelVersion("stub-v0");
        DetectTask child = task(2L, "修改稿", DetectConstants.STATUS_DONE, 12.0, LocalDateTime.of(2026, 10, 1, 9, 0));
        child.setParentTaskId(1L);
        when(taskRepository.findById(2L)).thenReturn(Optional.of(child));
        when(taskRepository.findById(1L)).thenReturn(Optional.of(parent));
        when(credentialService.fingerprint(child)).thenReturn("abcd1234abcd1234");
        when(credentialService.verifyUrl(child)).thenReturn("https://x/verify/RPT-2?code=zz");

        DetectTaskDetailVO vo = service.detail(2L);

        assertThat(vo.getReportFingerprint()).isEqualTo("abcd1234abcd1234");
        assertThat(vo.getVerifyUrl()).contains("/verify/");
        assertThat(vo.getParentAiRate()).isEqualTo(30.0);
        assertThat(vo.getParentPaperTitle()).isEqualTo("初稿");
        verify(credentialService).ensure(child);
    }

    /* ==================== §3.4 重试 ==================== */

    @Test
    @DisplayName("重试：原文件丢失 → 置 FAILED")
    void retryFileMissing() {
        DetectTask t = task(1L, "稿", DetectConstants.STATUS_DONE, 20.0, LocalDateTime.now());
        t.setFilePath("gone.txt");
        when(taskRepository.findById(1L)).thenReturn(Optional.of(t));
        when(storageService.exists("gone.txt")).thenReturn(false);

        DetectTask out = service.retry(1L);

        assertThat(out.getStatus()).isEqualTo(DetectConstants.STATUS_FAILED);
        verify(taskRepository).update(t);
    }

    @Test
    @DisplayName("重试：文件可读 → 重跑推理并回到 DONE")
    void retryRerunsInference() {
        DetectTask t = task(1L, "稿", DetectConstants.STATUS_FAILED, null, LocalDateTime.now());
        t.setFilePath("ok.txt");
        t.setOriginalFilename("ok.txt");
        when(taskRepository.findById(1L)).thenReturn(Optional.of(t));
        when(storageService.exists("ok.txt")).thenReturn(true);
        when(storageService.read("ok.txt")).thenReturn(
                new java.io.ByteArrayInputStream("body".getBytes(StandardCharsets.UTF_8)));
        when(textProcessor.extractText(any(), anyString())).thenReturn("body");
        when(textProcessor.splitParagraphs(anyString())).thenReturn(List.of("正文内容长度足够用于检测。"));
        when(textProcessor.filterNonBody(any())).thenReturn(List.of(meta("正文内容长度足够用于检测。", false, null)));
        when(inferenceClient.detectParagraph(anyString(), eq(true))).thenReturn(pyResult(0.6));

        DetectTask out = service.retry(1L);

        assertThat(out.getStatus()).isEqualTo(DetectConstants.STATUS_DONE);
        assertThat(out.getAiRate()).isEqualTo(60.0);
    }

    /* ==================== §3.5 / §3.6 ==================== */

    @Test
    @DisplayName("取消：置 FAILED")
    void cancelMarksFailed() {
        DetectTask t = task(1L, "稿", DetectConstants.STATUS_PENDING, null, LocalDateTime.now());
        when(taskRepository.findById(1L)).thenReturn(Optional.of(t));

        service.cancel(1L);

        assertThat(t.getStatus()).isEqualTo(DetectConstants.STATUS_FAILED);
        verify(taskRepository).update(t);
    }

    @Test
    @DisplayName("取消：任务不存在 → DETECT_TASK_NOT_FOUND")
    void cancelNotFound() {
        when(taskRepository.findById(1L)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> service.cancel(1L))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode())
                .isEqualTo(ErrorCode.DETECT_TASK_NOT_FOUND.getCode());
    }

    @Test
    @DisplayName("删除：删除存储文件并移除记录")
    void deleteRemovesFileAndRecord() {
        DetectTask t = task(5L, "稿", DetectConstants.STATUS_DONE, 10.0, LocalDateTime.now());
        t.setFilePath("s/5.txt");
        when(taskRepository.findById(5L)).thenReturn(Optional.of(t));

        service.delete(5L);

        verify(storageService).delete("s/5.txt");
        verify(taskRepository).deleteById(5L);
    }

    @Test
    @DisplayName("删除：任务不存在时静默返回")
    void deleteMissingIsNoop() {
        when(taskRepository.findById(5L)).thenReturn(Optional.empty());
        service.delete(5L);
        verify(taskRepository, never()).deleteById(anyLong());
    }

    /* ==================== §3.7 统计 ==================== */

    @Test
    @DisplayName("统计：今日 / 本月 / 总数 / 达标率 / 30 天趋势")
    void statisticsAggregates() {
        LocalDateTime today = LocalDateTime.now();
        DetectTask t1 = task(1L, "A", DetectConstants.STATUS_DONE, 10.0, today);
        t1.setThreshold(20);       // 达标
        DetectTask t2 = task(2L, "B", DetectConstants.STATUS_DONE, 40.0, today);
        t2.setThreshold(20);       // 超线
        DetectTask t3 = task(3L, "C", DetectConstants.STATUS_FAILED, null, today.minusDays(2));
        when(taskRepository.findAll()).thenReturn(List.of(t1, t2, t3));

        StatisticsVO vo = service.statistics();

        assertThat(vo.getTotal()).isEqualTo(3);
        assertThat(vo.getToday()).isEqualTo(2);
        assertThat(vo.getThisMonth()).isEqualTo(3);
        assertThat(vo.getDone()).isEqualTo(2);
        assertThat(vo.getAvgAiRate()).isEqualTo(25.0);
        assertThat(vo.getPassRate()).isEqualTo(50.0);
        assertThat(vo.getDailyTrend()).hasSize(30);
        assertThat(vo.getDailyTrend().get(29).getCount()).isEqualTo(2);   // 最后一天=今天
    }

    @Test
    @DisplayName("统计：无 DONE 任务时均值与达标率为 null")
    void statisticsEmptyRates() {
        when(taskRepository.findAll()).thenReturn(List.of(
                task(1L, "A", DetectConstants.STATUS_PENDING, null, LocalDateTime.now())));
        StatisticsVO vo = service.statistics();
        assertThat(vo.getAvgAiRate()).isNull();
        assertThat(vo.getPassRate()).isNull();
    }

    /* ==================== §4 / §8.2 / health ==================== */

    @Test
    @DisplayName("humanize：优先取任务段落原文")
    void humanizeUsesTaskParagraph() {
        DetectTask t = task(1L, "稿", DetectConstants.STATUS_DONE, 20.0, LocalDateTime.now());
        t.setParagraphs(List.of(
                com.paperaigc.detect.domain.entity.ParagraphResult.builder()
                        .paragraphIdx(0).text("任务里的原文").build()));
        when(taskRepository.findById(1L)).thenReturn(Optional.of(t));
        when(inferenceClient.humanize("任务里的原文", "academic")).thenReturn(Map.of(
                "rewritten_text", "改写后", "quality_score", 0.9, "model_version", "m1"));

        HumanizeDTO dto = new HumanizeDTO();
        dto.setTaskId(1L);
        dto.setParagraphIdx(0);

        Map<String, Object> resp = service.humanize(dto);

        assertThat(resp.get("originalText")).isEqualTo("任务里的原文");
        assertThat(resp.get("rewrittenText")).isEqualTo("改写后");
    }

    @Test
    @DisplayName("humanize：无 taskId 时用请求体 text")
    void humanizeUsesBodyText() {
        when(inferenceClient.humanize("自由文本", "casual")).thenReturn(Map.of("rewritten_text", "x"));
        HumanizeDTO dto = new HumanizeDTO();
        dto.setText("自由文本");
        dto.setStyle("casual");

        Map<String, Object> resp = service.humanize(dto);

        assertThat(resp.get("originalText")).isEqualTo("自由文本");
    }

    @Test
    @DisplayName("detectParagraph / inferenceHealth 直接透传推理客户端")
    void passthroughInference() {
        when(inferenceClient.detectParagraph("一段文本", false)).thenReturn(Map.of("calibrated_prob", 0.3));
        when(inferenceClient.health()).thenReturn(Map.of("status", "ok"));

        assertThat(service.detectParagraph("一段文本", false)).containsEntry("calibrated_prob", 0.3);
        assertThat(service.inferenceHealth()).containsEntry("status", "ok");
    }

    /* ==================== fixtures ==================== */

    private void stubTextPipeline() {
        when(textProcessor.extractText(any(MultipartFile.class))).thenReturn("body");
        when(textProcessor.splitParagraphs(anyString())).thenReturn(List.of("正文内容长度足够用于检测。"));
    }

    private static MultipartFile txt(String content) {
        return new MockMultipartFile("file", "paper.txt", "text/plain",
                content.getBytes(StandardCharsets.UTF_8));
    }

    private static Map<String, Object> meta(String text, boolean excluded, String reason) {
        Map<String, Object> m = new HashMap<>();
        m.put("text", text);
        m.put("excluded", excluded);
        if (reason != null) m.put("excludeReason", reason);
        m.put("sectionName", "正文");
        return m;
    }

    private static Map<String, Object> pyResult(double calibratedProb) {
        Map<String, Object> m = new HashMap<>();
        m.put("calibrated_prob", calibratedProb);
        m.put("ai_prob", calibratedProb - 0.05);
        m.put("interval", List.of(calibratedProb - 0.1, calibratedProb + 0.1));
        List<Map<String, Object>> sentences = new ArrayList<>();
        sentences.add(new HashMap<>(Map.of("sentence_idx", 0, "offset_start", 0, "offset_end", 4, "ai_prob", 0.7)));
        m.put("sentences", sentences);
        return m;
    }

    private static DetectTask task(Long id, String title, String status, Double aiRate, LocalDateTime createdAt) {
        return DetectTask.builder()
                .id(id).paperTitle(title).status(status).aiRate(aiRate)
                .scenario(ScenarioConstants.ACADEMIC_MASTER).modality(DetectConstants.MODALITY_TEXT)
                .createdAt(createdAt).build();
    }
}
