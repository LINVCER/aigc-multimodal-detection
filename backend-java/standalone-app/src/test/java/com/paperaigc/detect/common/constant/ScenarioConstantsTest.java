package com.paperaigc.detect.common.constant;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 场景阈值常量单元测试
 */
@DisplayName("ScenarioConstants · 场景阈值常量")
class ScenarioConstantsTest {

    @Test
    @DisplayName("各场景默认红线值符合运营口径")
    void defaultThresholds() {
        assertThat(ScenarioConstants.threshold(ScenarioConstants.ACADEMIC_BACHELOR)).isEqualTo(20);
        assertThat(ScenarioConstants.threshold(ScenarioConstants.ACADEMIC_MASTER)).isEqualTo(15);
        assertThat(ScenarioConstants.threshold(ScenarioConstants.ACADEMIC_PHD)).isEqualTo(10);
        assertThat(ScenarioConstants.threshold(ScenarioConstants.JOB_REPORT)).isEqualTo(15);
        assertThat(ScenarioConstants.threshold(ScenarioConstants.SELF_MEDIA)).isEqualTo(30);
        assertThat(ScenarioConstants.threshold(ScenarioConstants.OTHER)).isEqualTo(25);
    }

    @Test
    @DisplayName("未知场景兜底 OTHER(25)")
    void unknownFallsBackToOther() {
        assertThat(ScenarioConstants.threshold("not_exist")).isEqualTo(25);
        assertThat(ScenarioConstants.threshold(null)).isEqualTo(25);
    }

    @Test
    @DisplayName("degreeType 旧字段迁移到新场景码")
    void migrateDegreeType() {
        assertThat(ScenarioConstants.migrateDegreeType("BACHELOR")).isEqualTo(ScenarioConstants.ACADEMIC_BACHELOR);
        assertThat(ScenarioConstants.migrateDegreeType("MASTER")).isEqualTo(ScenarioConstants.ACADEMIC_MASTER);
        assertThat(ScenarioConstants.migrateDegreeType("PHD")).isEqualTo(ScenarioConstants.ACADEMIC_PHD);
        assertThat(ScenarioConstants.migrateDegreeType("UNKNOWN")).isEqualTo(ScenarioConstants.OTHER);
        assertThat(ScenarioConstants.migrateDegreeType(null)).isEqualTo(ScenarioConstants.OTHER);
    }

    @Test
    @DisplayName("label 展示名与兜底规则")
    void labels() {
        assertThat(ScenarioConstants.label(ScenarioConstants.ACADEMIC_MASTER)).isEqualTo("学术·硕士");
        assertThat(ScenarioConstants.label(ScenarioConstants.SELF_MEDIA)).isEqualTo("自媒体");
        assertThat(ScenarioConstants.label(null)).isEqualTo("-");
        assertThat(ScenarioConstants.label("  ")).isEqualTo("-");
        assertThat(ScenarioConstants.label("custom_scene")).isEqualTo("custom_scene");
    }
}
