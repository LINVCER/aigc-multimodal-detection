package com.paperaigc.detect.service.impl;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 文本处理组件单元测试 —— 格式校验 / 段落切分 / 非正文过滤
 */
@DisplayName("TextProcessor · 文本处理")
class TextProcessorTest {

    private final TextProcessor tp = new TextProcessor();

    @Nested
    @DisplayName("isAllowedFormat · 文件格式校验")
    class Format {

        @Test
        @DisplayName("MIME 命中白名单放行")
        void byMime() {
            assertThat(tp.isAllowedFormat(file("a.bin", "application/pdf", "x"))).isTrue();
        }

        @Test
        @DisplayName("MIME 不可靠时按后缀兜底")
        void byExt() {
            assertThat(tp.isAllowedFormat(file("a.docx", "application/octet-stream", "x"))).isTrue();
            assertThat(tp.isAllowedFormat(file("a.TXT", "application/octet-stream", "x"))).isTrue();
        }

        @Test
        @DisplayName("不在白名单的格式拒绝")
        void reject() {
            assertThat(tp.isAllowedFormat(file("a.exe", "application/x-msdownload", "x"))).isFalse();
            assertThat(tp.isAllowedFormat(file(null, "image/png", "x"))).isFalse();
        }
    }

    @Nested
    @DisplayName("splitParagraphs · 段落切分")
    class Split {

        @Test
        @DisplayName("null / 空白文本返回空列表")
        void blank() {
            assertThat(tp.splitParagraphs(null)).isEmpty();
            assertThat(tp.splitParagraphs("   \n  ")).isEmpty();
        }

        @Test
        @DisplayName("按空行分段，长段落各成一段")
        void byBlankLine() {
            String p1 = "第一段内容足够长用于测试分段逻辑这里再补一些字符使其超过三十个字符长度。";
            String p2 = "第二段内容同样足够长用于测试分段逻辑这里也补一些字符使其超过三十个字符长度。";
            List<String> out = tp.splitParagraphs(p1 + "\n\n" + p2);
            assertThat(out).hasSize(2);
            assertThat(out.get(0)).isEqualTo(p1);
            assertThat(out.get(1)).isEqualTo(p2);
        }

        @Test
        @DisplayName("CRLF 换行同样可切分")
        void crlf() {
            String p1 = "第一段内容足够长用于测试分段逻辑这里再补一些字符使其超过三十个字符长度。";
            String p2 = "第二段内容同样足够长用于测试分段逻辑这里也补一些字符使其超过三十个字符长度。";
            assertThat(tp.splitParagraphs(p1 + "\r\n\r\n" + p2)).hasSize(2);
        }

        @Test
        @DisplayName("过短段落合并，段数少于输入行数")
        void mergeShort() {
            String shortPara = "一二三四五六七八九十。";   // 11 字
            String text = String.join("\n\n", shortPara, shortPara, shortPara, shortPara);
            List<String> out = tp.splitParagraphs(text);
            assertThat(out).isNotEmpty();
            assertThat(out.size()).isLessThan(4);
        }

        @Test
        @DisplayName("超长段落（>800 字）按句末标点切分且不超限")
        void splitLong() {
            String unit = "a".repeat(99) + "。";     // 100 字/句
            String longPara = unit.repeat(10);        // 1000 字
            List<String> out = tp.splitParagraphs(longPara);
            assertThat(out.size()).isGreaterThan(1);
            assertThat(out).allSatisfy(p -> assertThat(p.length()).isLessThanOrEqualTo(800));
            assertThat(String.join("", out)).hasSize(1000);
        }
    }

    @Nested
    @DisplayName("filterNonBody · 非正文过滤")
    class Filter {

        private final List<String> raw = List.of(
                "摘要",
                "本文提出了一种新的检测方法，通过多模态融合提升准确率，并在多个数据集上验证了有效性。",
                "图1 系统总体架构示意图",
                "参考文献",
                "张三. 基于深度学习的文本检测. 计算机学报, 2020.",
                "[1] 李四. 另一篇论文. 2021.");

        @Test
        @DisplayName("章节标题识别并归一化章节名")
        void sectionTitle() {
            List<Map<String, Object>> out = tp.filterNonBody(raw);
            assertThat(out.get(0).get("excluded")).isEqualTo(true);
            assertThat(out.get(0).get("excludeReason")).isEqualTo("sectionTitle");
            assertThat(out.get(0).get("sectionName")).isEqualTo("摘要");
        }

        @Test
        @DisplayName("正文段落保留，继承当前章节名")
        void bodyKept() {
            List<Map<String, Object>> out = tp.filterNonBody(raw);
            assertThat(out.get(1).get("excluded")).isEqualTo(false);
            assertThat(out.get(1).get("sectionName")).isEqualTo("摘要");
        }

        @Test
        @DisplayName("图表 caption 识别为 caption")
        void caption() {
            List<Map<String, Object>> out = tp.filterNonBody(raw);
            assertThat(out.get(2).get("excluded")).isEqualTo(true);
            assertThat(out.get(2).get("excludeReason")).isEqualTo("caption");
        }

        @Test
        @DisplayName("命中「参考文献」后其后所有段落一并排除")
        void afterReferenceSection() {
            List<Map<String, Object>> out = tp.filterNonBody(raw);
            assertThat(out.get(3).get("excludeReason")).isEqualTo("reference");
            assertThat(out.get(3).get("sectionName")).isEqualTo("参考文献");
            assertThat(out.get(4).get("excluded")).isEqualTo(true);
            assertThat(out.get(5).get("excluded")).isEqualTo(true);
        }

        @Test
        @DisplayName("致谢起始段标注为 acknowledgement")
        void acknowledgement() {
            List<Map<String, Object>> out = tp.filterNonBody(List.of("致谢", "感谢导师的悉心指导与帮助。"));
            assertThat(out.get(0).get("excludeReason")).isEqualTo("acknowledgement");
            assertThat(out.get(0).get("sectionName")).isEqualTo("致谢");
            assertThat(out.get(1).get("excluded")).isEqualTo(true);
        }
    }

    private static MockMultipartFile file(String name, String mime, String content) {
        return new MockMultipartFile("file", name, mime, content.getBytes(StandardCharsets.UTF_8));
    }
}
