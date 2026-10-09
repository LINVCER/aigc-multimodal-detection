package com.paperaigc.detect.common.util;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.HashSet;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 密码 hash / 校验 / 临时密码 单元测试
 */
@DisplayName("PasswordHasher · 密码散列")
class PasswordHasherTest {

    @Test
    @DisplayName("hash 输出 salt:sha256 格式，salt 16 位、摘要 64 位十六进制")
    void hashFormat() {
        String stored = PasswordHasher.hash("P@ssw0rd");
        String[] parts = stored.split(":", 2);
        assertThat(parts).hasSize(2);
        assertThat(parts[0]).hasSize(16).matches("[0-9a-f]{16}");
        assertThat(parts[1]).hasSize(64).matches("[0-9a-f]{64}");
    }

    @Test
    @DisplayName("相同明文两次 hash 结果不同（随机 salt）")
    void saltRandomized() {
        assertThat(PasswordHasher.hash("same")).isNotEqualTo(PasswordHasher.hash("same"));
    }

    @Test
    @DisplayName("verify 正确明文通过")
    void verifyOk() {
        String stored = PasswordHasher.hash("Abc12345");
        assertThat(PasswordHasher.verify("Abc12345", stored)).isTrue();
    }

    @Test
    @DisplayName("verify 错误明文、null、无冒号格式均失败")
    void verifyFail() {
        String stored = PasswordHasher.hash("Abc12345");
        assertThat(PasswordHasher.verify("wrong", stored)).isFalse();
        assertThat(PasswordHasher.verify(null, stored)).isFalse();
        assertThat(PasswordHasher.verify("Abc12345", null)).isFalse();
        assertThat(PasswordHasher.verify("Abc12345", "nocolonhere")).isFalse();
    }

    @Test
    @DisplayName("tempPassword 长度 10 且同时含字母与数字")
    void tempPassword() {
        Set<String> seen = new HashSet<>();
        for (int i = 0; i < 200; i++) {
            String p = PasswordHasher.tempPassword();
            assertThat(p).hasSize(10);
            assertThat(p).matches(".*[A-Za-z].*");
            assertThat(p).matches(".*[0-9].*");
            seen.add(p);
        }
        // 200 次生成应基本无重复（随机性冒烟）
        assertThat(seen.size()).isGreaterThan(150);
    }
}
