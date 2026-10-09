package com.paperaigc.detect.controller;

import com.paperaigc.detect.common.constant.DetectConstants;
import com.paperaigc.detect.common.constant.ScenarioConstants;
import com.paperaigc.detect.common.exception.PaperAigcGlobalExceptionHandler;
import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.entity.ScenarioThreshold;
import com.paperaigc.detect.domain.vo.DetectTaskDetailVO;
import com.paperaigc.detect.domain.vo.DetectTaskVO;
import com.paperaigc.detect.domain.vo.PageVO;
import com.paperaigc.detect.domain.vo.StatisticsVO;
import com.paperaigc.detect.domain.vo.TaskCompareVO;
import com.paperaigc.detect.service.IDetectTaskService;
import com.paperaigc.detect.service.IScenarioThresholdService;
import com.paperaigc.detect.service.ITaskCompareService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 检测接口 HTTP 层测试 —— 路由 / 参数绑定 / 统一响应体 / 全局异常映射
 *
 * <p>用 standalone MockMvc 只装配 Controller + 全局异常处理器，Service 全 mock，
 * 不启 Spring 容器，保证快速且聚焦 HTTP 契约。</p>
 */
@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
@DisplayName("DetectController · 检测接口 HTTP 契约")
class DetectControllerTest {

    @Mock private IDetectTaskService detectTaskService;
    @Mock private IScenarioThresholdService scenarioThresholdService;
    @Mock private ITaskCompareService taskCompareService;

    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        DetectController controller = new DetectController(detectTaskService, scenarioThresholdService, taskCompareService);
        mockMvc = MockMvcBuilders.standaloneSetup(controller)
                .setControllerAdvice(new PaperAigcGlobalExceptionHandler())
                .build();
    }

    /* ==================== §3.1 提交 ==================== */

    @Test
    @DisplayName("POST /detect/submit → code=200 且回传 taskId / status")
    void submitReturnsTaskId() throws Exception {
        DetectTask task = DetectTask.builder()
                .id(88L).paperTitle("我的论文").status(DetectConstants.STATUS_DONE)
                .createdAt(LocalDateTime.of(2026, 10, 8, 12, 0)).build();
        when(detectTaskService.submit(any(), any(), any(), any(), any(), any(), any())).thenReturn(task);

        MockMultipartFile file = new MockMultipartFile("file", "paper.txt", "text/plain", "body".getBytes());

        mockMvc.perform(multipart("/api/v1/detect/submit")
                        .file(file)
                        .param("scenario", "academic_master")
                        .param("title", "我的论文"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.taskId").value(88))
                .andExpect(jsonPath("$.data.status").value("DONE"));
    }

    /* ==================== §3.2 列表 ==================== */

    @Test
    @DisplayName("GET /detect/tasks → 返回 {total, rows}")
    void listReturnsPage() throws Exception {
        DetectTaskVO row = DetectTaskVO.builder().id(1L).paperTitle("A").status("DONE").build();
        when(detectTaskService.page(any())).thenReturn(PageVO.of(1L, List.of(row)));

        mockMvc.perform(get("/api/v1/detect/tasks").param("pageNum", "1").param("pageSize", "20"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.total").value(1))
                .andExpect(jsonPath("$.data.rows[0].paperTitle").value("A"));
    }

    /* ==================== §3.3 详情 / 对比 ==================== */

    @Test
    @DisplayName("GET /detect/tasks/{id} → 返回详情")
    void detailReturns() throws Exception {
        when(detectTaskService.detail(5L)).thenReturn(DetectTaskDetailVO.builder()
                .id(5L).status("DONE").aiRate(12.5).reportNo("RPT-5").build());

        mockMvc.perform(get("/api/v1/detect/tasks/5"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.id").value(5))
                .andExpect(jsonPath("$.data.reportNo").value("RPT-5"));
    }

    @Test
    @DisplayName("GET /detect/tasks/{id}/compare → 返回对比视图")
    void compareReturns() throws Exception {
        when(taskCompareService.compare(5L)).thenReturn(TaskCompareVO.builder()
                .current(TaskCompareVO.Side.builder().id(5L).aiRate(12.0).build())
                .parent(TaskCompareVO.Side.builder().id(4L).aiRate(30.0).build())
                .comparable(true).build());

        mockMvc.perform(get("/api/v1/detect/tasks/5/compare"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.current.id").value(5))
                .andExpect(jsonPath("$.data.parent.id").value(4))
                .andExpect(jsonPath("$.data.comparable").value(true));
    }

    /* ==================== §3.4 / §3.5 / §3.6 ==================== */

    @Test
    @DisplayName("POST /detect/tasks/{id}/retry → 重试后返回最新详情")
    void retryReturnsDetail() throws Exception {
        when(detectTaskService.detail(5L)).thenReturn(DetectTaskDetailVO.builder().id(5L).status("DONE").build());

        mockMvc.perform(post("/api/v1/detect/tasks/5/retry"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("DONE"));
        verify(detectTaskService).retry(5L);
    }

    @Test
    @DisplayName("POST /detect/tasks/{id}/cancel → code=200 空数据")
    void cancelOk() throws Exception {
        mockMvc.perform(post("/api/v1/detect/tasks/5/cancel"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200));
        verify(detectTaskService).cancel(5L);
    }

    @Test
    @DisplayName("DELETE /detect/tasks/{id} → code=200")
    void deleteOk() throws Exception {
        mockMvc.perform(delete("/api/v1/detect/tasks/5"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200));
        verify(detectTaskService).delete(5L);
    }

    /* ==================== §3.7 统计 ==================== */

    @Test
    @DisplayName("GET /detect/statistics → 返回统计字段")
    void statisticsReturns() throws Exception {
        when(detectTaskService.statistics()).thenReturn(StatisticsVO.builder()
                .today(2).thisMonth(10).total(30).done(25).avgAiRate(18.5).passRate(72.0)
                .dailyTrend(List.of()).build());

        mockMvc.perform(get("/api/v1/detect/statistics"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total").value(30))
                .andExpect(jsonPath("$.data.avgAiRate").value(18.5));
    }

    /* ==================== §4 降 AIGC ==================== */

    @Test
    @DisplayName("POST /humanize → 返回改写结果")
    void humanizeReturns() throws Exception {
        when(detectTaskService.humanize(any())).thenReturn(Map.of(
                "originalText", "原文", "rewrittenText", "改写", "qualityScore", 0.9));

        mockMvc.perform(post("/api/v1/humanize")
                        .contentType("application/json")
                        .content("{\"text\":\"原文\",\"style\":\"academic\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.rewrittenText").value("改写"));
    }

    /* ==================== §8.2 单段检测 ==================== */

    @Test
    @DisplayName("POST /detect/paragraph 合法文本 → 透传推理结果")
    void detectParagraphOk() throws Exception {
        when(detectTaskService.detectParagraph(eq("这是一段待检测文本"), anyBoolean()))
                .thenReturn(Map.of("calibrated_prob", 0.72));

        mockMvc.perform(post("/api/v1/detect/paragraph")
                        .contentType("application/json")
                        .content("{\"text\":\"这是一段待检测文本\",\"returnSentences\":true}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.calibrated_prob").value(0.72));
    }

    @Test
    @DisplayName("POST /detect/paragraph 空文本 → 参数校验失败 code=1001")
    void detectParagraphBlankRejected() throws Exception {
        mockMvc.perform(post("/api/v1/detect/paragraph")
                        .contentType("application/json")
                        .content("{\"text\":\"\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(1001));
    }

    /* ==================== 阈值 / 健康 ==================== */

    @Test
    @DisplayName("GET /detect/scenario-thresholds → 返回启用配置列表")
    void scenarioThresholdsReturns() throws Exception {
        when(scenarioThresholdService.listAll()).thenReturn(List.of(
                ScenarioThreshold.builder().scenario(ScenarioConstants.ACADEMIC_MASTER)
                        .label("学术·硕士").threshold(new BigDecimal("15.00")).enabled(1).build()));

        mockMvc.perform(get("/api/v1/detect/scenario-thresholds"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[0].scenario").value("academic_master"))
                .andExpect(jsonPath("$.data[0].label").value("学术·硕士"));
    }

    @Test
    @DisplayName("GET /detect/health → 返回推理健康状态")
    void healthReturns() throws Exception {
        when(detectTaskService.inferenceHealth()).thenReturn(Map.of("status", "UP", "model", "stub-v0"));

        mockMvc.perform(get("/api/v1/detect/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("UP"));
    }
}
