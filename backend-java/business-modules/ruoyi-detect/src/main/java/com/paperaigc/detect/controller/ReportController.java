package com.paperaigc.detect.controller;

import com.itextpdf.io.font.FontProgram;
import com.itextpdf.io.font.FontProgramFactory;
import com.itextpdf.kernel.colors.ColorConstants;
import com.itextpdf.kernel.colors.DeviceRgb;
import com.itextpdf.kernel.font.PdfFont;
import com.itextpdf.kernel.font.PdfFontFactory;
import com.itextpdf.kernel.geom.PageSize;
import com.itextpdf.kernel.pdf.PdfDocument;
import com.itextpdf.kernel.pdf.PdfWriter;
import com.itextpdf.layout.Document;
import com.itextpdf.layout.borders.SolidBorder;
import com.itextpdf.layout.element.Cell;
import com.itextpdf.layout.element.LineSeparator;
import com.itextpdf.layout.element.Paragraph;
import com.itextpdf.layout.element.Table;
import com.itextpdf.layout.element.Text;
import com.itextpdf.layout.properties.HorizontalAlignment;
import com.itextpdf.layout.properties.TextAlignment;
import com.itextpdf.layout.properties.UnitValue;
import com.itextpdf.kernel.pdf.canvas.draw.SolidLine;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.io.OutputStream;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

/**
 * 报告导出（§5.2 下载）：iText 8 生成 PDF，含封面 + 溯源 + 段落表
 *
 * <p>为了不引入模板引擎与 CSS，直接用 iText Layout API 画；中文字体走 iText 内置
 * Adobe CJK STSong-Light（依赖 font-asian）无需额外 ttf。</p>
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/report")
public class ReportController {

    private final DetectController detectController;

    public ReportController(DetectController detectController) {
        this.detectController = detectController;
    }

    // 颜色常量（Apple systemXxx 对齐前端）
    private static final DeviceRgb C_PRIMARY = new DeviceRgb(0, 122, 255);
    private static final DeviceRgb C_GREEN   = new DeviceRgb(52, 199, 89);
    private static final DeviceRgb C_ORANGE  = new DeviceRgb(255, 149, 0);
    private static final DeviceRgb C_RED     = new DeviceRgb(255, 59, 48);
    private static final DeviceRgb C_GRAY    = new DeviceRgb(142, 142, 147);
    private static final DeviceRgb C_LABEL   = new DeviceRgb(28, 28, 30);
    private static final DeviceRgb C_MUTED   = new DeviceRgb(99, 99, 102);
    private static final DeviceRgb C_BG_SOFT = new DeviceRgb(242, 242, 247);

    @GetMapping("/tasks/{id}/pdf")
    public void downloadPdf(@PathVariable long id, HttpServletResponse response) throws Exception {
        Map<String, Object> task = detectController.getTaskRaw(id);
        if (task == null) {
            response.setStatus(404);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write("{\"code\":3003,\"msg\":\"任务不存在\"}");
            return;
        }

        String paperTitle = (String) task.getOrDefault("paperTitle", "未命名论文");
        String filename = URLEncoder.encode("AIGC检测报告-" + paperTitle + ".pdf", StandardCharsets.UTF_8)
                .replaceAll("\\+", "%20");
        response.setContentType("application/pdf");
        response.setHeader("Content-Disposition", "attachment; filename*=UTF-8''" + filename);

        try (OutputStream out = response.getOutputStream();
             PdfWriter writer = new PdfWriter(out);
             PdfDocument pdf = new PdfDocument(writer);
             Document doc = new Document(pdf, PageSize.A4)) {

            // 中文字体（iText 内置 Adobe CJK，无需 ttf）
            FontProgram fp = FontProgramFactory.createFont("STSong-Light", "UniGB-UCS2-H", true);
            PdfFont cn = PdfFontFactory.createFont(fp, PdfFontFactory.EmbeddingStrategy.PREFER_NOT_EMBEDDED);
            doc.setFont(cn).setFontSize(11).setFontColor(C_LABEL);

            renderCover(doc, task);
            renderSourceLabels(doc, task);
            renderParagraphTable(doc, task);
            renderFooter(doc, id);
        } catch (Exception e) {
            log.error("generate pdf failed for task {}", id, e);
            throw e;
        }
    }

    /* ==================== 封面 ==================== */

    private void renderCover(Document doc, Map<String, Object> task) {
        String paperTitle = str(task, "paperTitle", "未命名论文");
        String scenario   = str(task, "scenario", str(task, "degreeType", ""));
        String createdAt  = str(task, "createdAt", "");
        Number aiRateNum  = (Number) task.get("aiRate");
        Number threshold  = (Number) task.getOrDefault("threshold", 20);
        boolean done      = "DONE".equals(task.get("status"));

        // 平台名
        doc.add(new Paragraph("论文 AIGC 检测报告")
                .setFontSize(10).setFontColor(C_MUTED)
                .setTextAlignment(TextAlignment.CENTER)
                .setMarginTop(40).setMarginBottom(0));
        doc.add(new Paragraph("Paper AIGC Detection Report")
                .setFontSize(8).setFontColor(C_MUTED)
                .setTextAlignment(TextAlignment.CENTER).setMarginBottom(60));

        // 论文标题
        doc.add(new Paragraph(paperTitle)
                .setFontSize(22).setBold().setFontColor(C_LABEL)
                .setTextAlignment(TextAlignment.CENTER).setMarginBottom(80));

        // 主 AI 率大数字
        if (done && aiRateNum != null) {
            double aiRate = aiRateNum.doubleValue();
            double thr = threshold.doubleValue();
            DeviceRgb color = rateColor(aiRate, thr);
            boolean pass = aiRate <= thr;

            doc.add(new Paragraph("整体 AI 率")
                    .setFontSize(10).setFontColor(C_MUTED)
                    .setTextAlignment(TextAlignment.CENTER).setMarginBottom(4));
            doc.add(new Paragraph(String.format("%.1f%%", aiRate))
                    .setFontSize(72).setBold().setFontColor(color)
                    .setTextAlignment(TextAlignment.CENTER).setMarginBottom(8));
            doc.add(new Paragraph(pass
                    ? "✓  低于红线 " + threshold + "%，达标"
                    : "⚠  超过红线 " + threshold + "%，建议修改后重检")
                    .setFontSize(12).setBold().setFontColor(color)
                    .setTextAlignment(TextAlignment.CENTER).setMarginBottom(40));
        } else {
            doc.add(new Paragraph("尚未完成 / 检测失败").setFontSize(14).setFontColor(C_GRAY)
                    .setTextAlignment(TextAlignment.CENTER).setMarginBottom(40));
        }

        // 元信息表
        Table meta = new Table(UnitValue.createPercentArray(new float[]{1, 2}))
                .useAllAvailableWidth()
                .setMarginLeft(60).setMarginRight(60).setMarginTop(20);
        addMetaRow(meta, "使用场景", scenarioLabel(scenario) + "  ·  红线 ≤ " + threshold + "%");
        addMetaRow(meta, "检测时间", createdAt);
        addMetaRow(meta, "论文段落", task.getOrDefault("bodyParagraphCount", "-") + " 正文 / "
                + task.getOrDefault("excludedParagraphCount", 0) + " 已排除");
        addMetaRow(meta, "字符数",   String.valueOf(task.getOrDefault("wordCount", "-")));
        addMetaRow(meta, "模型版本", str(task, "modelVersion", "stub-v0"));
        doc.add(meta);

        doc.add(new Paragraph("\n").setFontSize(1));
        doc.add(new LineSeparator(new SolidLine(0.5f)).setMarginTop(30));
        doc.add(new Paragraph("说明：AI 率仅计算正文段落，已自动排除参考文献、致谢、附录、章节标题、图/表标题。")
                .setFontSize(8).setFontColor(C_MUTED).setMarginTop(8));
    }

    private void addMetaRow(Table t, String k, String v) {
        Cell key = new Cell().add(new Paragraph(k)).setFontColor(C_MUTED).setFontSize(10)
                .setBorder(null).setPaddingTop(6).setPaddingBottom(6);
        Cell val = new Cell().add(new Paragraph(v)).setFontColor(C_LABEL).setFontSize(10)
                .setBorder(null).setPaddingTop(6).setPaddingBottom(6);
        t.addCell(key); t.addCell(val);
    }

    /* ==================== 溯源分布 ==================== */

    @SuppressWarnings("unchecked")
    private void renderSourceLabels(Document doc, Map<String, Object> task) {
        Map<String, Number> labels = (Map<String, Number>) task.get("sourceLabels");
        if (labels == null || labels.isEmpty()) return;

        doc.add(new Paragraph("\n\n"));
        doc.add(new Paragraph("疑似来源分布")
                .setFontSize(14).setBold().setFontColor(C_LABEL).setMarginBottom(12));

        Table t = new Table(UnitValue.createPercentArray(new float[]{2, 5, 1}))
                .useAllAvailableWidth();
        labels.entrySet().stream()
                .sorted((a, b) -> Double.compare(b.getValue().doubleValue(), a.getValue().doubleValue()))
                .forEach(e -> {
                    double ratio = e.getValue().doubleValue();
                    // 名字
                    t.addCell(new Cell()
                            .add(new Paragraph(sourceName(e.getKey())))
                            .setBorder(null).setFontSize(10).setPaddingTop(4).setPaddingBottom(4));
                    // 简易条形（用空格文字宽度模拟）
                    int cells = (int) Math.round(ratio * 40);
                    StringBuilder bar = new StringBuilder();
                    for (int i = 0; i < cells; i++) bar.append('█');
                    t.addCell(new Cell()
                            .add(new Paragraph(bar.toString()).setFontColor(sourceColor(e.getKey())))
                            .setBorder(null).setFontSize(8).setPaddingTop(4).setPaddingBottom(4));
                    // 百分比
                    t.addCell(new Cell()
                            .add(new Paragraph(String.format("%.0f%%", ratio * 100)))
                            .setBorder(null).setFontSize(10).setTextAlignment(TextAlignment.RIGHT)
                            .setPaddingTop(4).setPaddingBottom(4));
                });
        doc.add(t);
    }

    /* ==================== 段落表 ==================== */

    @SuppressWarnings("unchecked")
    private void renderParagraphTable(Document doc, Map<String, Object> task) {
        List<Map<String, Object>> paragraphs = (List<Map<String, Object>>) task.get("paragraphs");
        if (paragraphs == null || paragraphs.isEmpty()) return;

        doc.add(new Paragraph("\n\n"));
        doc.add(new Paragraph("段落分析")
                .setFontSize(14).setBold().setFontColor(C_LABEL).setMarginBottom(12));

        Table t = new Table(UnitValue.createPercentArray(new float[]{0.6f, 1.2f, 1.4f, 8}))
                .useAllAvailableWidth();

        // 表头
        addHeaderCell(t, "段");
        addHeaderCell(t, "AI 率");
        addHeaderCell(t, "疑似来源");
        addHeaderCell(t, "段落文本（前 120 字）");

        for (Map<String, Object> p : paragraphs) {
            int idx = ((Number) p.get("paragraphIdx")).intValue();
            String text = (String) p.get("text");
            boolean excluded = Boolean.TRUE.equals(p.get("excluded"));
            String excludeReason = (String) p.get("excludeReason");
            Number cp = (Number) p.get("calibratedProb");
            String source = (String) p.get("sourceLabel");

            // idx
            t.addCell(new Cell().add(new Paragraph(String.valueOf(idx + 1)))
                    .setBorder(new SolidBorder(C_BG_SOFT, 0.5f))
                    .setFontSize(9).setFontColor(C_MUTED).setPadding(6));

            // AI 率
            if (excluded) {
                t.addCell(new Cell().add(new Paragraph("—"))
                        .setBorder(new SolidBorder(C_BG_SOFT, 0.5f))
                        .setFontSize(9).setFontColor(C_GRAY).setPadding(6));
            } else if (cp != null) {
                double rate = cp.doubleValue() * 100;
                DeviceRgb color = probColor(cp.doubleValue());
                t.addCell(new Cell()
                        .add(new Paragraph(String.format("%.0f%%", rate)).setBold().setFontColor(color))
                        .setBorder(new SolidBorder(C_BG_SOFT, 0.5f)).setFontSize(10).setPadding(6));
            } else {
                t.addCell(new Cell().add(new Paragraph("-"))
                        .setBorder(new SolidBorder(C_BG_SOFT, 0.5f)).setFontSize(9).setPadding(6));
            }

            // 来源 / excluded 徽章
            String sourceCell;
            DeviceRgb sourceColor = C_MUTED;
            if (excluded) {
                sourceCell = "已排除·" + excludeReasonLabel(excludeReason);
                sourceColor = C_GRAY;
            } else if (source != null && !"human".equals(source)) {
                sourceCell = "疑似 " + sourceName(source);
                sourceColor = sourceColor(source);
            } else {
                sourceCell = "人类";
                sourceColor = C_GREEN;
            }
            t.addCell(new Cell().add(new Paragraph(sourceCell).setFontColor(sourceColor))
                    .setBorder(new SolidBorder(C_BG_SOFT, 0.5f))
                    .setFontSize(9).setPadding(6));

            // 段落文本
            String preview = text == null ? ""
                    : (text.length() > 120 ? text.substring(0, 120) + "…" : text);
            Cell textCell = new Cell().add(new Paragraph(preview))
                    .setBorder(new SolidBorder(C_BG_SOFT, 0.5f))
                    .setFontSize(9).setPadding(6);
            if (excluded) textCell.setFontColor(C_GRAY);
            t.addCell(textCell);
        }

        doc.add(t);
    }

    private void addHeaderCell(Table t, String label) {
        t.addHeaderCell(new Cell()
                .add(new Paragraph(label).setBold())
                .setBackgroundColor(C_BG_SOFT)
                .setBorder(null)
                .setFontSize(9).setFontColor(C_MUTED).setPadding(8));
    }

    /* ==================== 页脚 ==================== */

    private void renderFooter(Document doc, long id) {
        doc.add(new Paragraph("\n"));
        doc.add(new LineSeparator(new SolidLine(0.5f)));
        doc.add(new Paragraph(new Text("检测编号：#" + id + "  ·  由 paper-aigc-detect 平台生成  ·  报告仅供参考"))
                .setFontSize(8).setFontColor(C_MUTED)
                .setTextAlignment(TextAlignment.CENTER).setMarginTop(8));
    }

    /* ==================== helpers ==================== */

    private DeviceRgb rateColor(double rate, double threshold) {
        if (rate <= threshold) return C_GREEN;
        if (rate <= threshold * 1.5) return C_ORANGE;
        return C_RED;
    }

    private DeviceRgb probColor(double prob) {
        if (prob >= 0.7) return C_RED;
        if (prob >= 0.4) return C_ORANGE;
        return C_GREEN;
    }

    private DeviceRgb sourceColor(String s) {
        if (s == null) return C_MUTED;
        return switch (s) {
            case "human" -> C_GREEN;
            case "qwen" -> C_ORANGE;
            case "gpt" -> new DeviceRgb(175, 82, 222);       // systemPurple
            case "claude" -> new DeviceRgb(255, 45, 85);     // systemPink
            case "deepseek" -> C_PRIMARY;
            case "glm" -> new DeviceRgb(90, 200, 250);       // systemTeal
            case "kimi" -> new DeviceRgb(175, 82, 222);
            case "ernie" -> C_RED;
            default -> C_MUTED;
        };
    }

    private String sourceName(String s) {
        if (s == null) return "未知";
        return switch (s) {
            case "human" -> "人类";
            case "gpt" -> "GPT";
            case "claude" -> "Claude";
            case "qwen" -> "通义千问";
            case "deepseek" -> "DeepSeek";
            case "glm" -> "智谱GLM";
            case "kimi" -> "Kimi";
            case "ernie" -> "文心";
            default -> "其他";
        };
    }

    private String scenarioLabel(String s) {
        if (s == null || s.isBlank()) return "-";
        return switch (s) {
            case "academic_bachelor" -> "学术·本科";
            case "academic_master"   -> "学术·硕士";
            case "academic_phd"      -> "学术·博士";
            case "job_report"        -> "职业报告";
            case "self_media"        -> "自媒体";
            case "other"             -> "其他";
            // 兼容旧数据
            case "BACHELOR" -> "学术·本科";
            case "MASTER"   -> "学术·硕士";
            case "PHD"      -> "学术·博士";
            default -> s;
        };
    }

    private String excludeReasonLabel(String r) {
        if (r == null) return "非正文";
        return switch (r) {
            case "reference" -> "参考文献";
            case "acknowledgement" -> "致谢";
            case "appendix" -> "附录";
            case "sectionTitle" -> "章节标题";
            case "caption" -> "图表标题";
            default -> "非正文";
        };
    }

    private String str(Map<String, Object> m, String k, String dft) {
        Object v = m.get(k);
        return v == null ? dft : v.toString();
    }
}
