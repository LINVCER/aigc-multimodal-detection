package com.paperaigc.detect.common.constant;

import java.util.Set;

/**
 * 用户反馈常量（W3.d）
 *
 * <p>对齐 {@code scripts/patch-schema.sql} 的 user_feedback 表 status / category 枚举。</p>
 */
public final class FeedbackConstants {

    private FeedbackConstants() {}

    /* ---------- category ---------- */
    public static final String CATEGORY_BUG        = "bug";
    public static final String CATEGORY_SUGGESTION = "suggestion";
    public static final String CATEGORY_APPEAL     = "appeal";
    public static final Set<String> CATEGORIES = Set.of(CATEGORY_BUG, CATEGORY_SUGGESTION, CATEGORY_APPEAL);

    /* ---------- status ---------- */
    public static final String STATUS_PENDING    = "PENDING";
    public static final String STATUS_PROCESSING = "PROCESSING";
    public static final String STATUS_REPLIED    = "REPLIED";
    public static final String STATUS_IGNORED    = "IGNORED";
    public static final Set<String> STATUSES = Set.of(
            STATUS_PENDING, STATUS_PROCESSING, STATUS_REPLIED, STATUS_IGNORED
    );

    /** 反馈内容最大字符数 */
    public static final int CONTENT_MAX_LEN = 2000;
    /** 联系方式最大字符数 */
    public static final int CONTACT_MAX_LEN = 128;
}
