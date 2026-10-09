package com.paperaigc.detect.common.enums;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 业务错误码单元测试 —— 保证编码唯一、文案非空、分段规则正确
 */
@DisplayName("ErrorCode · 业务错误码")
class ErrorCodeTest {

    @Test
    @DisplayName("所有错误码数值唯一")
    void codesUnique() {
        Set<Integer> codes = Arrays.stream(ErrorCode.values())
                .map(ErrorCode::getCode)
                .collect(Collectors.toSet());
        assertThat(codes).hasSize(ErrorCode.values().length);
    }

    @Test
    @DisplayName("所有错误码文案非空")
    void msgNotBlank() {
        for (ErrorCode ec : ErrorCode.values()) {
            assertThat(ec.getMsg()).as("code=%s", ec.name()).isNotBlank();
        }
    }

    @Test
    @DisplayName("关键错误码数值符合分段约定")
    void keyCodes() {
        assertThat(ErrorCode.PARAM_INVALID.getCode()).isEqualTo(1001);
        assertThat(ErrorCode.UNAUTHORIZED.getCode()).isEqualTo(1401);
        assertThat(ErrorCode.LOGIN_PASSWORD_WRONG.getCode()).isEqualTo(2003);
        assertThat(ErrorCode.REGISTER_USERNAME_EXISTS.getCode()).isEqualTo(2004);
        assertThat(ErrorCode.AUTH_RATE_LIMITED.getCode()).isEqualTo(2429);
        assertThat(ErrorCode.DETECT_FILE_TOO_LARGE.getCode()).isEqualTo(3001);
        assertThat(ErrorCode.DETECT_TASK_NOT_FOUND.getCode()).isEqualTo(3003);
        assertThat(ErrorCode.FEEDBACK_CONTENT_TOO_LONG.getCode()).isEqualTo(4003);
        assertThat(ErrorCode.ASSISTANT_RATE_LIMITED.getCode()).isEqualTo(7429);
    }

    @Test
    @DisplayName("错误码数值均在 4 位区间内且不重复前缀段")
    void codeRange() {
        Set<Integer> seen = new HashSet<>();
        for (ErrorCode ec : ErrorCode.values()) {
            int c = ec.getCode();
            assertThat(c).isBetween(1000, 9999);
            assertThat(seen.add(c)).as("duplicated code %d", c).isTrue();
        }
    }
}
