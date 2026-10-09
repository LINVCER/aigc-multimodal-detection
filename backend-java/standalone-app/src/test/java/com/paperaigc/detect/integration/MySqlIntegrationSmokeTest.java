package com.paperaigc.detect.integration;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.entity.ParagraphResult;
import com.paperaigc.detect.domain.entity.ScenarioThreshold;
import com.paperaigc.detect.domain.entity.SentenceResult;
import com.paperaigc.detect.mapper.DetectParagraphResultMapper;
import com.paperaigc.detect.mapper.DetectSentenceResultMapper;
import com.paperaigc.detect.repository.IDetectTaskRepository;
import com.paperaigc.detect.repository.IScenarioThresholdRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.DatabaseMetaData;
import java.sql.ResultSet;
import java.sql.Statement;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * MySQL 集成冒烟测试 —— 真实 DataSource + Mapper + Repository
 *
 * <p>目的：验证部署环境中 MySQL 的连通性、表结构存在性、MyBatis-Plus 主子表事务与
 * JSON 列类型处理器在真实数据库上的行为。单测（全 Mock）覆盖不到这些。</p>
 *
 * <p>默认不参与 {@code mvn test}（被 Surefire 按 {@code @Tag("integration")} 排除）。
 * 运行：{@code mvn test -Pintegration -Dtest=MySqlIntegrationSmokeTest}</p>
 *
 * <p>连接参数见 {@code src/test/resources/application-integration.yml}，可用
 * {@code SMOKE_MYSQL_*} 环境变量覆盖。</p>
 *
 * <p>数据安全：所有写入均带 {@value #TITLE_PREFIX} 前缀，用例结束在 {@code @AfterEach}
 * 按 id 物理删除，不触碰库中既有数据。</p>
 */
@Tag("integration")
@SpringBootTest(classes = com.paperaigc.app.PaperAigcApplication.class,
        webEnvironment = SpringBootTest.WebEnvironment.NONE)
@ActiveProfiles("integration")
@DisplayName("MySQL 集成冒烟 · 真实库连通与主子表读写")
class MySqlIntegrationSmokeTest {

    private static final String TITLE_PREFIX = "SMOKE-IT-";

    @Autowired private DataSource dataSource;
    @Autowired private IDetectTaskRepository taskRepository;
    @Autowired private IScenarioThresholdRepository thresholdRepository;
    @Autowired private DetectParagraphResultMapper paragraphMapper;
    @Autowired private DetectSentenceResultMapper sentenceMapper;

    private final List<Long> createdTaskIds = new ArrayList<>();

    @AfterEach
    void cleanUp() {
        createdTaskIds.forEach(id -> {
            try {
                taskRepository.deleteById(id);
            } catch (Exception ignored) {
                // 清理尽力而为，不掩盖断言失败
            }
        });
        createdTaskIds.clear();
    }

    /* ==================== 连通性 ==================== */

    @Test
    @DisplayName("DataSource 能建立真实连接，且连接到目标库")
    void dataSourceConnectsToRealMysql() throws Exception {
        try (Connection conn = dataSource.getConnection()) {
            assertThat(conn.isValid(3)).isTrue();

            DatabaseMetaData meta = conn.getMetaData();
            assertThat(meta.getDatabaseProductName()).containsIgnoringCase("MySQL");
            // 库名来自 application-integration.yml（默认 ry-vue）
            assertThat(conn.getCatalog()).isEqualTo("ry-vue");

            try (Statement st = conn.createStatement();
                 ResultSet rs = st.executeQuery("SELECT VERSION()")) {
                assertThat(rs.next()).isTrue();
                assertThat(rs.getString(1)).isNotBlank();
            }
        }
    }

    @Test
    @DisplayName("核心业务表均已建好（detect_task / 阈值 / 段 / 句）")
    void coreTablesExist() throws Exception {
        List<String> expected = List.of(
                "detect_task", "detect_scenario_threshold",
                "detect_paragraph_result", "detect_sentence_result");

        try (Connection conn = dataSource.getConnection();
             Statement st = conn.createStatement()) {
            for (String table : expected) {
                try (ResultSet rs = st.executeQuery(
                        "SELECT COUNT(*) FROM information_schema.TABLES "
                                + "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '" + table + "'")) {
                    assertThat(rs.next()).isTrue();
                    assertThat(rs.getInt(1))
                            .as("表 %s 应存在于当前库", table)
                            .isEqualTo(1);
                }
            }
        }
    }

    /* ==================== 阈值配置（只读） ==================== */

    @Test
    @DisplayName("场景阈值：启用行可读且含 academic_master 种子数据")
    void scenarioThresholdSeededRowsReadable() {
        List<ScenarioThreshold> enabled = thresholdRepository.findAllEnabled();
        assertThat(enabled).isNotEmpty();
        assertThat(enabled).allSatisfy(t -> {
            assertThat(t.getScenario()).isNotBlank();
            assertThat(t.getThreshold()).isNotNull();
            assertThat(t.getEnabled()).isEqualTo(1);
        });

        Optional<ScenarioThreshold> master = thresholdRepository.findByScenario("academic_master");
        assertThat(master).isPresent();
        assertThat(master.get().getThreshold().intValue()).isPositive();
    }

    /* ==================== 主子表事务 + JSON 列 ==================== */

    @Test
    @DisplayName("detect_task 主子表写入 → 读回组装 → 更新替换子表 → 删除级联")
    void detectTaskRoundTripWithChildren() {
        DetectTask task = newTask("round-trip");
        task.setSourceLabels(Map.of("qwen", 0.72, "gptzero", 0.18));
        task.setParagraphs(List.of(
                paragraph(0, "第一段正文内容，用于验证段落落库与读回。", List.of(
                        sentence(0, "第一句。", 0.61),
                        sentence(1, "第二句。", 0.58))),
                paragraph(1, "第二段正文内容，用于验证段落排序。", List.of(
                        sentence(0, "第三句。", 0.44)))));

        DetectTask saved = taskRepository.save(task);
        createdTaskIds.add(saved.getId());
        assertThat(saved.getId()).isNotNull();

        DetectTask loaded = taskRepository.findById(saved.getId()).orElseThrow();

        // 主表字段 + JSON 列反序列化
        assertThat(loaded.getPaperTitle()).isEqualTo(task.getPaperTitle());
        assertThat(loaded.getStatus()).isEqualTo("done");
        assertThat(loaded.getAiRate()).isEqualTo(12.34);
        assertThat(loaded.getSourceLabels())
                .containsEntry("qwen", 0.72)
                .containsEntry("gptzero", 0.18);

        // 子表按 paragraph_idx 升序组装，句按 sentence_idx 升序
        assertThat(loaded.getParagraphs()).hasSize(2);
        ParagraphResult p0 = loaded.getParagraphs().get(0);
        assertThat(p0.getParagraphIdx()).isZero();
        assertThat(p0.getConfidenceInterval()).isInstanceOf(List.class);
        assertThat((List<?>) p0.getConfidenceInterval()).hasSize(2);
        assertThat(p0.getWarnings()).containsExactly("low_confidence", "short_text");
        assertThat(p0.getSentences()).hasSize(2);
        assertThat(p0.getSentences().get(0).getSentenceIdx()).isZero();
        assertThat(loaded.getParagraphs().get(1).getSentences()).hasSize(1);

        // 更新：替换子表（删旧插新）
        loaded.setAiRate(66.66);
        loaded.setParagraphs(List.of(
                paragraph(0, "更新后的唯一段落。", List.of(sentence(0, "唯一句。", 0.9)))));
        Optional<DetectTask> updated = taskRepository.update(loaded);
        assertThat(updated).isPresent();

        DetectTask afterUpdate = taskRepository.findById(saved.getId()).orElseThrow();
        assertThat(afterUpdate.getAiRate()).isEqualTo(66.66);
        assertThat(afterUpdate.getParagraphs()).hasSize(1);
        assertThat(afterUpdate.getParagraphs().get(0).getText()).isEqualTo("更新后的唯一段落。");
        assertThat(countParagraphs(saved.getId())).isEqualTo(1);
        assertThat(countSentences(saved.getId())).isEqualTo(1);

        // 删除：主子表一并清理
        assertThat(taskRepository.deleteById(saved.getId())).isTrue();
        assertThat(taskRepository.findById(saved.getId())).isEmpty();
        assertThat(countParagraphs(saved.getId())).isZero();
        assertThat(countSentences(saved.getId())).isZero();
        createdTaskIds.clear();
    }

    @Test
    @DisplayName("findAll 按 createdAt 倒序返回真实行")
    void findAllOrdersByCreatedAtDesc() {
        DetectTask older = newTask("older");
        older.setCreatedAt(LocalDateTime.now().minusMinutes(5));
        DetectTask newer = newTask("newer");
        newer.setCreatedAt(LocalDateTime.now());
        createdTaskIds.add(taskRepository.save(older).getId());
        createdTaskIds.add(taskRepository.save(newer).getId());

        List<DetectTask> all = new ArrayList<>(taskRepository.findAll());

        assertThat(all).isNotEmpty();
        for (int i = 1; i < all.size(); i++) {
            LocalDateTime prev = all.get(i - 1).getCreatedAt();
            LocalDateTime cur = all.get(i).getCreatedAt();
            assertThat(prev).isAfterOrEqualTo(cur);
        }
        // 新建的 newer 应排在 older 之前
        List<Long> ids = all.stream().map(DetectTask::getId).toList();
        assertThat(ids.indexOf(newer.getId())).isLessThan(ids.indexOf(older.getId()));
    }

    /* ==================== helpers ==================== */

    private DetectTask newTask(String tag) {
        return DetectTask.builder()
                .modality("text")
                .paperTitle(TITLE_PREFIX + tag + "-" + System.nanoTime())
                .status("done")
                .scenario("academic_master")
                .threshold(15)
                .aiRate(12.34)
                .wordCount(128)
                .bodyParagraphCount(2L)
                .excludedParagraphCount(0)
                .build();
    }

    private ParagraphResult paragraph(int idx, String text, List<SentenceResult> sentences) {
        return ParagraphResult.builder()
                .paragraphIdx(idx)
                .text(text)
                .excluded(false)
                .aiProb(0.5)
                .calibratedProb(0.55)
                .confidenceInterval(List.of(0.45, 0.65))
                .sourceLabel("qwen")
                .sectionName("正文")
                .warnings(List.of("low_confidence", "short_text"))
                .sentences(sentences)
                .build();
    }

    private SentenceResult sentence(int idx, String text, double aiProb) {
        return SentenceResult.builder()
                .sentenceIdx(idx)
                .text(text)
                .aiProb(aiProb)
                .build();
    }

    private long countParagraphs(Long taskId) {
        return paragraphMapper.selectCount(Wrappers.lambdaQuery(ParagraphResult.class)
                .eq(ParagraphResult::getTaskId, taskId));
    }

    private long countSentences(Long taskId) {
        return sentenceMapper.selectCount(Wrappers.lambdaQuery(SentenceResult.class)
                .eq(SentenceResult::getTaskId, taskId));
    }
}
