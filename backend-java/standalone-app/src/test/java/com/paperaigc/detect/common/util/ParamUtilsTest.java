package com.paperaigc.detect.common.util;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 参数取值工具单元测试 —— 覆盖 null 与类型转换边界
 */
@DisplayName("ParamUtils · 参数取值工具")
class ParamUtilsTest {

    @Nested
    @DisplayName("str · 字符串取值")
    class Str {

        @Test
        @DisplayName("正常取值返回 String.valueOf")
        void returnsValue() {
            Map<String, Object> m = new HashMap<>();
            m.put("k", 123);
            assertThat(ParamUtils.str(m, "k")).isEqualTo("123");
        }

        @Test
        @DisplayName("map 为 null 或键不存在返回 null")
        void returnsNull() {
            assertThat(ParamUtils.str(null, "k")).isNull();
            assertThat(ParamUtils.str(new HashMap<>(), "k")).isNull();
        }

        @Test
        @DisplayName("带默认值：缺失时返回默认值")
        void returnsDefault() {
            assertThat(ParamUtils.str(new HashMap<>(), "k", "def")).isEqualTo("def");
            Map<String, Object> m = new HashMap<>();
            m.put("k", "v");
            assertThat(ParamUtils.str(m, "k", "def")).isEqualTo("v");
        }
    }

    @Nested
    @DisplayName("toLong · 转 Long")
    class ToLong {

        @Test
        @DisplayName("Number 直接取 longValue")
        void fromNumber() {
            assertThat(ParamUtils.toLong(12)).isEqualTo(12L);
            assertThat(ParamUtils.toLong(3.9d)).isEqualTo(3L);
        }

        @Test
        @DisplayName("数字字符串可解析")
        void fromString() {
            assertThat(ParamUtils.toLong("42")).isEqualTo(42L);
        }

        @Test
        @DisplayName("null 与非数字串返回 null")
        void invalid() {
            assertThat(ParamUtils.toLong(null)).isNull();
            assertThat(ParamUtils.toLong("abc")).isNull();
        }
    }

    @Nested
    @DisplayName("toInt / toDouble")
    class ToNumber {

        @Test
        @DisplayName("toInt 正常与异常路径")
        void toInt() {
            assertThat(ParamUtils.toInt(7)).isEqualTo(7);
            assertThat(ParamUtils.toInt("8")).isEqualTo(8);
            assertThat(ParamUtils.toInt("x")).isNull();
            assertThat(ParamUtils.toInt(null)).isNull();
        }

        @Test
        @DisplayName("toDouble 正常与异常路径")
        void toDouble() {
            assertThat(ParamUtils.toDouble("1.5")).isEqualTo(1.5d);
            assertThat(ParamUtils.toDouble(2)).isEqualTo(2.0d);
            assertThat(ParamUtils.toDouble("x")).isNull();
            assertThat(ParamUtils.toDouble(null)).isNull();
        }
    }

    @Test
    @DisplayName("containsIgnoreCase · 大小写不敏感包含")
    void containsIgnoreCase() {
        assertThat(ParamUtils.containsIgnoreCase("Hello World", "WORLD")).isTrue();
        assertThat(ParamUtils.containsIgnoreCase("abc", "z")).isFalse();
        assertThat(ParamUtils.containsIgnoreCase(null, "a")).isFalse();
        assertThat(ParamUtils.containsIgnoreCase("a", null)).isFalse();
    }

    @Test
    @DisplayName("isBlank · 空白判定")
    void isBlank() {
        assertThat(ParamUtils.isBlank(null)).isTrue();
        assertThat(ParamUtils.isBlank("")).isTrue();
        assertThat(ParamUtils.isBlank("   ")).isTrue();
        assertThat(ParamUtils.isBlank("a")).isFalse();
    }
}
