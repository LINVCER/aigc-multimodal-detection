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

    /* ---------- 模态 ---------- */
    public static final String MODALITY_TEXT  = "text";
    public static final String MODALITY_AUDIO = "audio";
    public static final String MODALITY_IMAGE = "image";
    public static final Set<String> MODALITIES = Set.of(MODALITY_TEXT, MODALITY_AUDIO, MODALITY_IMAGE);

    /* ---------- 文件校验 ---------- */
    public static final long FILE_SIZE_MAX       = 20L * 1024 * 1024;   // 20MB · 文本
    public static final long FILE_SIZE_MAX_AUDIO = 50L * 1024 * 1024;   // 50MB · 音频
    public static final long FILE_SIZE_MAX_IMAGE = 20L * 1024 * 1024;   // 20MB · 图像

    /** 文本 MIME 白名单 */
    public static final Set<String> ALLOWED_MIME = Set.of(
            "application/pdf",
            "application/msword",                                                        // .doc
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",   // .docx
            "text/plain",
            "application/octet-stream"                                                   // 小程序常报此 MIME，靠后缀兜
    );

    /** 文本后缀白名单（MIME 不可靠时兜底） */
    public static final Set<String> ALLOWED_EXT = Set.of("pdf", "doc", "docx", "txt");

    /** 音频 MIME 白名单 */
    public static final Set<String> ALLOWED_AUDIO_MIME = Set.of(
            "audio/mpeg",       // mp3
            "audio/mp4",        // m4a
            "audio/x-m4a",
            "audio/wav",
            "audio/x-wav",
            "audio/flac",
            "audio/ogg",
            "audio/webm",
            "application/octet-stream"
    );

    /** 音频后缀白名单 */
    public static final Set<String> ALLOWED_AUDIO_EXT = Set.of("mp3", "m4a", "wav", "flac", "ogg", "webm");

    /** 图像 MIME 白名单 */
    public static final Set<String> ALLOWED_IMAGE_MIME = Set.of(
            "image/jpeg",
            "image/png",
            "image/webp",
            "image/gif",
            "image/bmp",
            "application/octet-stream"
    );

    /** 图像后缀白名单 */
    public static final Set<String> ALLOWED_IMAGE_EXT = Set.of("jpg", "jpeg", "png", "webp", "gif", "bmp");

    /* ---------- 任务状态 ---------- */
    public static final String STATUS_PENDING = "PENDING";
    public static final String STATUS_RUNNING = "RUNNING";
    public static final String STATUS_DONE    = "DONE";
    public static final String STATUS_FAILED  = "FAILED";
    public static final Set<String> STATUSES = Set.of(STATUS_PENDING, STATUS_RUNNING, STATUS_DONE, STATUS_FAILED);

    /**
     * 按后缀猜测模态；未知返回 text
     * @param filename 原始文件名
     * @return modality (text / audio / image)
     */
    public static String guessModality(String filename) {
        if (filename == null) return MODALITY_TEXT;
        int dot = filename.lastIndexOf('.');
        if (dot < 0 || dot >= filename.length() - 1) return MODALITY_TEXT;
        String ext = filename.substring(dot + 1).toLowerCase();
        if (ALLOWED_AUDIO_EXT.contains(ext)) return MODALITY_AUDIO;
        if (ALLOWED_IMAGE_EXT.contains(ext)) return MODALITY_IMAGE;
        if (ALLOWED_EXT.contains(ext)) return MODALITY_TEXT;
        return MODALITY_TEXT;
    }
}
