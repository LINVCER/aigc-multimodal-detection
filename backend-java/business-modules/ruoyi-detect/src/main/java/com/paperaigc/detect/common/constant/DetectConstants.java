package com.paperaigc.detect.common.constant;

import java.util.Set;

/**
 * 检测任务常量
 *
 * <p>包含格式白名单 + 大小限制 + 状态字面量，供 Service / Controller 复用，
 * 不在业务代码里散落硬编码。</p>
 */
public final class DetectConstants {

    private DetectConstants() {}

    /* ---------- 文件校验 ---------- */
    public static final long FILE_SIZE_MAX = 20L * 1024 * 1024;     // 20MB

    /** MIME 白名单 */
    public static final Set<String> ALLOWED_MIME = Set.of(
            "application/pdf",
            "application/msword",                                                        // .doc
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",   // .docx
            "text/plain",
            "application/octet-stream"                                                   // 小程序常报此 MIME，靠后缀兜
    );

    /** 后缀白名单（MIME 不可靠时兜底） */
    public static final Set<String> ALLOWED_EXT = Set.of("pdf", "doc", "docx", "txt");

    /* ---------- 任务状态 ---------- */
    public static final String STATUS_PENDING = "PENDING";
    public static final String STATUS_RUNNING = "RUNNING";
    public static final String STATUS_DONE    = "DONE";
    public static final String STATUS_FAILED  = "FAILED";
    public static final Set<String> STATUSES = Set.of(STATUS_PENDING, STATUS_RUNNING, STATUS_DONE, STATUS_FAILED);
}
