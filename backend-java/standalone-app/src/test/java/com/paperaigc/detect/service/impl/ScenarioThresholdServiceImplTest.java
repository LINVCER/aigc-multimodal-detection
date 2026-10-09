package com.paperaigc.detect.service.impl;

import com.paperaigc.detect.domain.entity.ScenarioThreshold;
import com.paperaigc.detect.repository.IScenarioThresholdRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;

import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 场景阈值服务单元测试 —— DB 覆盖 / 常量兜底 / 缓存失效
 */
@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
@DisplayName("ScenarioThresholdServiceImpl · 场景阈值服务")
class ScenarioThresholdServiceImplTest {

    @Mock private IScenarioThresholdRepository repository;

    private ScenarioThresholdServiceImpl service;

    @BeforeEach
    void setUp() {
        service = new ScenarioThresholdServiceImpl(repository);
    }

    @Test
    @DisplayName("DB 无配置 → 回退 ScenarioConstants 默认值")
    void fallbackToConstants() {
        when(repository.findByScenario("academic_phd")).thenReturn(Optional.empty());
        assertThat(service.threshold("academic_phd")).isEqualTo(10);
    }

    @Test
    @DisplayName("DB 有配置 → 取 DB 值并 HALF_UP 取整")
    void dbOverride() {
        when(repository.findByScenario("academic_master"))
                .thenReturn(Optional.of(row("academic_master", "12.6", "学术·硕士")));
        assertThat(service.threshold("academic_master")).isEqualTo(13);
        assertThat(service.label("academic_master")).isEqualTo("学术·硕士");
    }

    @Test
    @DisplayName("scenario 为空 → 兜底 OTHER(25)")
    void blankScenario() {
        assertThat(service.threshold(null)).isEqualTo(25);
        assertThat(service.threshold("   ")).isEqualTo(25);
    }

    @Test
    @DisplayName("label：DB 为空时回退常量展示名")
    void labelFallback() {
        when(repository.findByScenario("academic_bachelor")).thenReturn(Optional.empty());
        assertThat(service.label("academic_bachelor")).isEqualTo("学术·本科");
    }

    @Test
    @DisplayName("updateThreshold 后缓存失效，读取到新值")
    void updateInvalidatesCache() {
        when(repository.findByScenario("academic_master"))
                .thenReturn(Optional.of(row("academic_master", "15", null)));
        assertThat(service.threshold("academic_master")).isEqualTo(15);   // 首次读 DB 并缓存

        // DB 变了但缓存未失效 → 仍返回旧值
        when(repository.findByScenario("academic_master"))
                .thenReturn(Optional.of(row("academic_master", "9", null)));
        assertThat(service.threshold("academic_master")).isEqualTo(15);

        service.updateThreshold("academic_master", 9, true);
        verify(repository).update(any(ScenarioThreshold.class));
        assertThat(service.threshold("academic_master")).isEqualTo(9);    // 缓存已失效
    }

    @Test
    @DisplayName("listAll 直接委托仓储")
    void listAll() {
        List<ScenarioThreshold> rows = List.of(row("other", "25", "其他"));
        when(repository.findAllEnabled()).thenReturn(rows);
        assertThat(service.listAll()).isSameAs(rows);
    }

    private static ScenarioThreshold row(String scenario, String threshold, String label) {
        return ScenarioThreshold.builder()
                .scenario(scenario)
                .threshold(new BigDecimal(threshold))
                .label(label)
                .enabled(1)
                .build();
    }
}
