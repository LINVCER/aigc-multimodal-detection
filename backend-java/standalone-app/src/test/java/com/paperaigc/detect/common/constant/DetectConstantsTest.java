package com.paperaigc.detect.common.constant;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 检测任务常量单元测试
 */
@DisplayName("DetectConstants · 检测常量")
class DetectConstantsTest {

    @Test
    @DisplayName("后缀白名单仅含 pdf/doc/docx/txt")
    void allowedExt() {
        assertThat(DetectConstants.ALLOWED_EXT).containsExactlyInAnyOrder("pdf", "doc", "docx", "txt");
        assertThat(DetectConstants.ALLOWED_EXT).doesNotContain("exe");
    }

    @Test
    @DisplayName("MIME 白名单含 pdf / docx / octet-stream")
    void allowedMime() {
        assertThat(DetectConstants.ALLOWED_MIME).contains(
                "application/pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/octet-stream");
    }

    @Test
    @DisplayName("大小限制为 20MB")
    void sizeLimit() {
        assertThat(DetectConstants.FILE_SIZE_MAX).isEqualTo(20L * 1024 * 1024);
    }

    @Test
    @DisplayName("状态集合含 4 个状态")
    void statuses() {
        assertThat(DetectConstants.STATUSES)
                .containsExactlyInAnyOrder("PENDING", "RUNNING", "DONE", "FAILED");
    }

    @Test
    @DisplayName("当前仅文本模态")
    void modality() {
        assertThat(DetectConstants.MODALITIES).containsExactly("text");
        assertThat(DetectConstants.guessModality("any.pdf")).isEqualTo("text");
        assertThat(DetectConstants.guessModality(null)).isEqualTo("text");
    }
}
