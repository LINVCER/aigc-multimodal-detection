package com.paperaigc.detect.common.constant;

import java.util.Map;

/**
 * 场景 / 阈值常量（W3.b 使用场景取代学位红线）
 *
 * <p>对齐 {@code docs/design/OPERATIONS_REQUIREMENTS.md §3.7} 与
 * {@code scripts/patch-schema.sql} 的 detect_scenario_threshold 表初值。</p>
 * <p>接入 DB 后，运营后台改阈值走 detect_scenario_threshold 覆盖此默认值；
 * 但代码兜底常量保留，避免配置表清空时后端断服。</p>
 */
public final class ScenarioConstants {

    private ScenarioConstants() {}

    public static final String ACADEMIC_BACHELOR = "academic_bachelor";
    public static final String ACADEMIC_MASTER   = "academic_master";
    public static final String ACADEMIC_PHD      = "academic_phd";
    public static final String JOB_REPORT        = "job_report";
    public static final String SELF_MEDIA        = "self_media";
    public static final String OTHER             = "other";

    /** 场景 → AI 率红线默认值（%） */
    public static final Map<String, Integer> DEFAULT_THRESHOLD = Map.of(
            ACADEMIC_BACHELOR, 20,
            ACADEMIC_MASTER,   15,
            ACADEMIC_PHD,      10,
            JOB_REPORT,        15,
            SELF_MEDIA,        30,
            OTHER,             25
    );

    /** 场景 → 展示名（跟前端 SCENARIO_MAP.label 一致） */
    public static final Map<String, String> LABEL = Map.of(
            ACADEMIC_BACHELOR, "学术·本科",
            ACADEMIC_MASTER,   "学术·硕士",
            ACADEMIC_PHD,      "学术·博士",
            JOB_REPORT,        "职业报告",
            SELF_MEDIA,        "自媒体",
            OTHER,             "其他"
    );

    /** 兼容旧字段 degreeType（BACHELOR/MASTER/PHD） → 新场景码 */
    public static String migrateDegreeType(String degreeType) {
        if (degreeType == null) return OTHER;
        return switch (degreeType) {
            case "BACHELOR" -> ACADEMIC_BACHELOR;
            case "MASTER"   -> ACADEMIC_MASTER;
            case "PHD"      -> ACADEMIC_PHD;
            default         -> OTHER;
        };
    }

    /**
     * 取场景的默认阈值；未知场景兜底 OTHER
     * @param scenario 场景码
     * @return AI 率红线（%）
     */
    public static int threshold(String scenario) {
        return DEFAULT_THRESHOLD.getOrDefault(scenario, DEFAULT_THRESHOLD.get(OTHER));
    }

    /**
     * 取场景展示名；未知场景兜底 OTHER 或原样返回
     * @param scenario 场景码
     * @return 展示名
     */
    public static String label(String scenario) {
        if (scenario == null || scenario.isBlank()) return "-";
        return LABEL.getOrDefault(scenario, scenario);
    }
}
