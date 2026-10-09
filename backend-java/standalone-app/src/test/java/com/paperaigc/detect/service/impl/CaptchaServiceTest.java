package com.paperaigc.detect.service.impl;

import com.paperaigc.detect.domain.vo.CaptchaVO;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 图形验证码单元测试 —— 生成 / 校验 / 一次性消费
 */
@DisplayName("CaptchaService · 图形验证码")
class CaptchaServiceTest {

    private final CaptchaService service = new CaptchaService();

    @Test
    @DisplayName("generate 返回非空 captchaId 与 PNG data URI")
    void generate() {
        CaptchaVO vo = service.generate();
        assertThat(vo.getCaptchaId()).isNotBlank();
        assertThat(vo.getImageBase64()).startsWith("data:image/png;base64,");
        assertThat(vo.getImageBase64().length()).isGreaterThan(100);
    }

    @Test
    @DisplayName("两次生成 captchaId 不同")
    void uniqueIds() {
        assertThat(service.generate().getCaptchaId()).isNotEqualTo(service.generate().getCaptchaId());
    }

    @Test
    @DisplayName("null / 未知 id 校验失败")
    void invalidInputs() {
        assertThat(service.verify(null, null)).isFalse();
        assertThat(service.verify("nope", "ABCD")).isFalse();
        CaptchaVO vo = service.generate();
        assertThat(service.verify(vo.getCaptchaId(), null)).isFalse();
    }

    @Test
    @DisplayName("正确验证码通过（不区分大小写），且一次性消费")
    void verifyAndConsume() throws Exception {
        CaptchaVO vo = service.generate();
        String real = peekCode(vo.getCaptchaId());

        // 大小写不敏感
        assertThat(service.verify(vo.getCaptchaId(), real.toLowerCase())).isTrue();
        // 已消费，再次校验失败
        assertThat(service.verify(vo.getCaptchaId(), real)).isFalse();
    }

    @Test
    @DisplayName("错误验证码失败")
    void wrongCode() throws Exception {
        CaptchaVO vo = service.generate();
        String real = peekCode(vo.getCaptchaId());
        String wrong = "AAAA".equals(real) ? "BBBB" : "AAAA";
        assertThat(service.verify(vo.getCaptchaId(), wrong)).isFalse();
    }

    /** 白盒：反射读取内存中的真实验证码，用于构造正向用例 */
    @SuppressWarnings("unchecked")
    private String peekCode(String captchaId) throws Exception {
        Field f = CaptchaService.class.getDeclaredField("store");
        f.setAccessible(true);
        Map<String, Object> store = (Map<String, Object>) f.get(service);
        Object entry = store.get(captchaId);
        Method m = entry.getClass().getDeclaredMethod("code");
        m.setAccessible(true);
        return (String) m.invoke(entry);
    }
}
