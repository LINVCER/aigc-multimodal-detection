package com.paperaigc.detect.service.impl;

import com.paperaigc.detect.common.constant.DetectConstants;
import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import lombok.extern.slf4j.Slf4j;
import org.apache.tika.Tika;
import org.apache.tika.metadata.Metadata;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.io.InputStream;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * 文本处理组件（Tika 抽取 · 段落切分 · 非正文过滤三合一）
 *
 * <p>无状态，所有正则常量类内声明。原 DetectController 的三个 private 方法 + 五个 Pattern 静态字段
 * 全部收敛在此，Controller / Service 都不再感知具体规则。</p>
 */
@Slf4j
@Component
public class TextProcessor {

    /** Tika 线程安全，可长期复用 */
    private final Tika tika = new Tika();

    /* ==================== 正则常量 ==================== */

    /** 参考文献 / 致谢 / 附录 起始段：命中后其后所有段落一并排除 */
    private static final Pattern REF_START = Pattern.compile(
            "^\\s*(参考\\s*文献|references?|bibliography|致\\s*谢|acknowledge?ments?|附\\s*录|appendix)\\s*$",
            Pattern.CASE_INSENSITIVE);

    /** 章节标题：短段 + 中/英数字前缀或常见节名 */
    private static final Pattern SECTION_TITLE = Pattern.compile(
            "^\\s*(第[一二三四五六七八九十百千0-9]+[章节篇]|chapter\\s+\\d+|\\d+(\\.\\d+)*\\s+\\S{1,20}|摘\\s*要|abstract|引\\s*言|introduction|结\\s*论|conclusion|讨\\s*论|discussion|方\\s*法|methods?|背\\s*景|background|相关工作|related\\s+work|实\\s*验|experiments?|结\\s*果|results?)\\s*$",
            Pattern.CASE_INSENSITIVE);

    /** 图/表/公式 caption：段首匹配 */
    private static final Pattern CAPTION = Pattern.compile(
            "^\\s*(图|表|figure|table|fig\\.|tab\\.|公式|equation|eq\\.)\\s*\\d",
            Pattern.CASE_INSENSITIVE);

    /** 单条参考文献 */
    private static final Pattern REF_ITEM = Pattern.compile(
            "^\\s*(\\[\\d+\\]|\\(\\d+\\)|\\d+\\.)\\s+\\S");

    /* ==================== 文件格式校验 ==================== */

    /** MIME + 后缀双重校验，任一通过即放行 */
    public boolean isAllowedFormat(MultipartFile file) {
        String mime = file.getContentType();
        String ext = "";
        String name = file.getOriginalFilename();
        if (name != null) {
            int dot = name.lastIndexOf('.');
            if (dot >= 0 && dot < name.length() - 1) ext = name.substring(dot + 1).toLowerCase();
        }
        return (mime != null && DetectConstants.ALLOWED_MIME.contains(mime))
                || DetectConstants.ALLOWED_EXT.contains(ext);
    }

    /* ==================== Tika 抽取 ==================== */

    /** 抽全文，单次最大 1MB（MultipartFile 版） */
    public String extractText(MultipartFile file) {
        try (InputStream is = file.getInputStream()) {
            return tika.parseToString(is, new Metadata(), 1_000_000);
        } catch (Exception e) {
            log.error("extract text failed: {}", file.getOriginalFilename(), e);
            throw new BizException(ErrorCode.DETECT_EXTRACT_FAILED, e.getMessage());
        }
    }

    /** 抽全文（InputStream 版，供 retry 时从 storage 反读原稿） */
    public String extractText(InputStream is, String filenameForLog) {
        try (InputStream in = is) {
            return tika.parseToString(in, new Metadata(), 1_000_000);
        } catch (Exception e) {
            log.error("extract text failed: {}", filenameForLog, e);
            throw new BizException(ErrorCode.DETECT_EXTRACT_FAILED, e.getMessage());
        }
    }

    /* ==================== 段落切分 ==================== */

    /**
     * 优先按空行分段；过短段合并、过长段（>800 字）按中英句末标点切
     */
    public List<String> splitParagraphs(String text) {
        List<String> out = new ArrayList<>();
        if (text == null || text.isBlank()) return out;

        String norm = text.replace("\r\n", "\n").replace("\r", "\n");
        StringBuilder buf = new StringBuilder();
        for (String raw : norm.split("\n\\s*\n")) {
            String p = raw.replaceAll("[\\t ]+", " ").trim();
            if (p.isEmpty()) continue;

            if (p.length() < 30) {
                if (buf.length() > 0) buf.append(' ');
                buf.append(p);
                if (buf.length() >= 30) { out.add(buf.toString()); buf.setLength(0); }
                continue;
            }
            if (buf.length() > 0) { out.add(buf + " " + p); buf.setLength(0); }
            else out.add(p);
        }
        if (buf.length() > 0) out.add(buf.toString());

        List<String> normalized = new ArrayList<>();
        for (String p : out) {
            if (p.length() <= 800) { normalized.add(p); continue; }
            StringBuilder chunk = new StringBuilder();
            for (int i = 0; i < p.length(); i++) {
                char c = p.charAt(i);
                chunk.append(c);
                boolean isEnd = c == '。' || c == '！' || c == '？' || c == '.' || c == '!' || c == '?';
                if (isEnd && chunk.length() >= 400) {
                    normalized.add(chunk.toString().trim());
                    chunk.setLength(0);
                }
            }
            if (chunk.length() > 0) normalized.add(chunk.toString().trim());
        }
        return normalized;
    }

    /* ==================== 非正文过滤 ==================== */

    /**
     * 给每段打 {text, excluded, excludeReason, sectionName}
     * <p>命中「参考文献 / 致谢 / 附录」起始后，其后所有段落 excluded=true。</p>
     */
    public List<Map<String, Object>> filterNonBody(List<String> raw) {
        List<Map<String, Object>> out = new ArrayList<>(raw.size());
        boolean afterRefSection = false;
        String afterReason = null;
        String currentSection = "正文";

        for (String text : raw) {
            String reason = null;

            if (!afterRefSection && REF_START.matcher(text).matches()) {
                afterRefSection = true;
                boolean isAck = text.matches("(?i).*致谢.*") || text.matches("(?i).*acknowledge.*");
                boolean isAppendix = text.matches("(?i).*附录.*") || text.matches("(?i).*appendix.*");
                afterReason = isAck ? "acknowledgement" : isAppendix ? "appendix" : "reference";
                reason = afterReason;
                currentSection = isAck ? "致谢" : isAppendix ? "附录" : "参考文献";
            } else if (afterRefSection) {
                reason = afterReason;
            } else if (SECTION_TITLE.matcher(text).matches() && text.length() < 30) {
                reason = "sectionTitle";
                currentSection = normalizeSectionName(text.trim());
            } else if (CAPTION.matcher(text).find()) {
                reason = "caption";
            } else if (REF_ITEM.matcher(text).find() && text.length() < 300) {
                reason = "reference";
            }

            Map<String, Object> meta = new HashMap<>();
            meta.put("text", text);
            meta.put("excluded", reason != null);
            if (reason != null) meta.put("excludeReason", reason);
            meta.put("sectionName", currentSection);
            out.add(meta);
        }
        return out;
    }

    /** 章节名归一化：英文常见节名映射为中文规范名 */
    private String normalizeSectionName(String raw) {
        String s = raw.replaceAll("\\s+", " ").trim();
        String lower = s.toLowerCase();
        if (lower.equals("abstract")) return "摘要";
        if (lower.equals("introduction")) return "引言";
        if (lower.equals("background")) return "背景";
        if (lower.equals("related work") || lower.equals("relatedwork")) return "相关工作";
        if (lower.startsWith("methods") || lower.equals("method")) return "方法";
        if (lower.startsWith("experiments") || lower.equals("experiment")) return "实验";
        if (lower.startsWith("results") || lower.equals("result")) return "结果";
        if (lower.startsWith("discussion")) return "讨论";
        if (lower.equals("conclusion") || lower.equals("conclusions")) return "结论";
        return s;
    }
}
