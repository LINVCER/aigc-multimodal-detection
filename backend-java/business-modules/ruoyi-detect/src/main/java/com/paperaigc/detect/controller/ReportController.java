package com.paperaigc.detect.controller;

import cn.dev33.satoken.annotation.SaIgnore;
import com.itextpdf.io.font.FontProgram;
import com.itextpdf.io.font.FontProgramFactory;
import com.itextpdf.kernel.colors.DeviceRgb;
import com.itextpdf.kernel.font.PdfFont;
import com.itextpdf.kernel.font.PdfFontFactory;
import com.itextpdf.kernel.geom.PageSize;
import com.itextpdf.kernel.pdf.PdfDocument;
import com.itextpdf.kernel.pdf.PdfWriter;
import com.itextpdf.kernel.pdf.canvas.draw.SolidLine;
import com.itextpdf.layout.Document;
import com.itextpdf.layout.borders.SolidBorder;
import com.itextpdf.layout.element.Cell;
import com.itextpdf.layout.element.LineSeparator;
import com.itextpdf.layout.element.Paragraph;
import com.itextpdf.layout.element.Table;
import com.itextpdf.layout.element.Text;
import com.itextpdf.layout.properties.TextAlignment;
import com.itextpdf.layout.properties.UnitValue;
import com.paperaigc.detect.common.constant.DetectConstants;
import com.paperaigc.detect.common.constant.ScenarioConstants;
import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.entity.ParagraphResult;
import com.paperaigc.detect.repository.IDetectTaskRepository;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.io.OutputStream;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;

/**
 * 报告导出（§5.2 下载）：iText 8 生成 PDF
 *
 * <p>字段全部从 DetectTask entity 读取，不再依赖 DetectController Map。
 * 中文字体走 iText 内置 Adobe CJK STSong-Light（依赖 font-asian）无需额外 ttf。</p>
 */
@Slf4j
@SaIgnore
@RestController
@RequestMapping("/api/v1/report")
@RequiredArgsConstructor
public class ReportController {

    private final IDetectTaskRepository taskRepository;

    private static final DeviceRgb C_PRIMARY = new DeviceRgb(0, 122, 255);
    private static final DeviceRgb C_GREEN   = new DeviceRgb(52, 199, 89);
    private static final DeviceRgb C_ORANGE  = new DeviceRgb(255, 149, 0);
    private static final DeviceRgb C_RED     = new DeviceRgb(255, 59, 48);
    private static final DeviceRgb C_GRAY    = new DeviceRgb(142, 142, 147);
    private static final DeviceRgb C_LABEL   = new DeviceRgb(28, 28, 30);
    private static final DeviceRgb C_MUTED   = new DeviceRgb(99, 99, 102);
    private static final DeviceRgb C_BG_SOFT = new DeviceRgb(242, 242, 247);

    private static final DateTimeFormatter FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    @GetMapping("/tasks/{id}/pdf")
    public void downloadPdf(@PathVariable long id, HttpServletResponse response) throws Exception {
        DetectTask task = taskRepository.findById(id).orElse(null);
        if (task == null) {
            response.setStatus(404);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write("{\"code\":" + ErrorCode.DETECT_TASK_NOT_FOUND.getCode()
                    + ",\"msg\":\"" + ErrorCode.DETECT_TASK_NOT_FOUND.getMsg() + "\"}");
            return;
        }

        String paperTitle = task.getPaperTitle() == null ? "未命名论文" : task.getPaperTitle();
        String filename = URLEncoder.encode("AIGC检测报告-" + paperTitle + ".pdf", StandardCharsets.UTF_8)
                .replaceAll("\\+", "%20");
        response.setContentType("application/pdf");
        response.setHeader("Content-Disposition", "attachment; filename*=UTF-8''" + filename);

        try (OutputStream out = response.getOutputStream();
             PdfWriter writer = new PdfWriter(out);
             PdfDocument pdf = new PdfDocument(writer);
             Document doc = new Document(pdf, PageSize.A4)) {

            FontProgram fp = FontProgramFactory.createFont("STSong-Light", "UniGB-UCS2-H", true);
            PdfFont cn = PdfFontFactory.createFont(fp, "UniGB-UCS2-H");
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

    private void renderCover(Document doc, DetectTask task) {
        String paperTitle = task.getPaperTitle() == null ? "未命名论文" : task.getPaperTitle();
        Integer threshold = task.getThreshold() == null ? 20 : task.getThreshold();
        Double  aiRate    = task.getAiRate();
        boolean done      = DetectConstants.STATUS_DONE.equals(task.getStatus());

        doc.add(new Paragraph("论文 AIGC 检测报告")
                .setFontSize(10).setFontColor(C_MUTED)
                .setTextAlignment(TextAlignment.CENTER)
                .setMarginTop(40).setMarginBottom(0));
        doc.add(new Paragraph("Paper AIGC Detection Report")
                .setFontSize(8).setFontColor(C_MUTED)
                .setTextAlignment(TextAlignment.CENTER).setMarginBottom(60));

        doc.add(new Paragraph(paperTitle)
                .setFontSize(22).setBold().setFontColor(C_LABEL)
                .setTextAlignment(TextAlignment.CENTER).setMarginBottom(80));

        if (done && aiRate != null) {
            DeviceRgb color = rateColor(aiRate, threshold);
            boolean pass = aiRate <= threshold;
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

        String createdAt = task.getCreatedAt() == null ? "-" : task.getCreatedAt().format(FMT);
        String bodyPara = String.valueOf(task.getBodyParagraphCount() == null ? "-" : task.getBodyParagraphCount());
        int excludedPara = task.getExcludedParagraphCount() == null ? 0 : task.getExcludedParagraphCount();

        Table meta = new Table(UnitValue.createPercentArray(new float[]{1, 2}))
                .useAllAvailableWidth()
                .setMarginLeft(60).setMarginRight(60).setMarginTop(20);
        addMetaRow(meta, "使用场景", ScenarioConstants.label(task.getScenario()) + "  ·  红线 ≤ " + threshold + "%");
        addMetaRow(meta, "检测时间", createdAt);
        addMetaRow(meta, "论文段落", bodyPara + " 正文 / " + excludedPara + " 已排除");
        addMetaRow(meta, "字符数",   String.valueOf(task.getWordCount() == null ? "-" : task.getWordCount()));
        addMetaRow(meta, "模型版本", task.getModelVersion() == null ? "stub-v0" : task.getModelVersion());
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

    private void renderSourceLabels(Document doc, DetectTask task) {
        Map<String, Double> labels = task.getSourceLabels();
        if (labels == null || labels.isEmpty()) return;

        doc.add(new Paragraph("\n\n"));
        doc.add(new Paragraph("疑似来源分布")
                .setFontSize(14).setBold().setFontColor(C_LABEL).setMarginBottom(12));

        Table t = new Table(UnitValue.createPercentArray(new float[]{2, 5, 1}))
                .useAllAvailableWidth();
        labels.entrySet().stream()
                .sorted((a, b) -> Double.compare(b.getValue(), a.getValue()))
                .forEach(e -> {
                    double ratio = e.getValue();
                    t.addCell(new Cell().add(new Paragraph(sourceName(e.getKey())))
                            .setBorder(null).setFontSize(10).setPaddingTop(4).setPaddingBottom(4));
                    int cells = (int) Math.round(ratio * 40);
                    StringBuilder bar = new StringBuilder();
                    for (int i = 0; i < cells; i++) bar.append('█');
                    t.addCell(new Cell().add(new Paragraph(bar.toString()).setFontColor(sourceColor(e.getKey())))
                            .setBorder(null).setFontSize(8).setPaddingTop(4).setPaddingBottom(4));
                    t.addCell(new Cell().add(new Paragraph(String.format("%.0f%%", ratio * 100)))
                            .setBorder(null).setFontSize(10).setTextAlignment(TextAlignment.RIGHT)
                            .setPaddingTop(4).setPaddingBottom(4));
                });
        doc.add(t);
    }

    /* ==================== 段落表 ==================== */

    private void renderParagraphTable(Document doc, DetectTask task) {
        List<ParagraphResult> paragraphs = task.getParagraphs();
        if (paragraphs == null || paragraphs.isEmpty()) return;

        doc.add(new Paragraph("\n\n"));
        doc.add(new Paragraph("段落分析")
                .setFontSize(14).setBold().setFontColor(C_LABEL).setMarginBottom(12));

        Table t = new Table(UnitValue.createPercentArray(new float[]{0.6f, 1.2f, 1.4f, 8}))
                .useAllAvailableWidth();

        addHeaderCell(t, "段");
        addHeaderCell(t, "AI 率");
        addHeaderCell(t, "疑似来源");
        addHeaderCell(t, "段落文本（前 120 字）");

        for (ParagraphResult p : paragraphs) {
            int idx = p.getParagraphIdx() == null ? 0 : p.getParagraphIdx();
            String text = p.getText();
            boolean excluded = p.isExcluded();
            String excludeReason = p.getExcludeReason();
            Double cp = p.getCalibratedProb();
            String source = p.getSourceLabel();

            t.addCell(new Cell().add(new Paragraph(String.valueOf(idx + 1)))
                    .setBorder(new SolidBorder(C_BG_SOFT, 0.5f))
                    .setFontSize(9).setFontColor(C_MUTED).setPadding(6));

            if (excluded) {
                t.addCell(new Cell().add(new Paragraph("—"))
                        .setBorder(new SolidBorder(C_BG_SOFT, 0.5f))
                        .setFontSize(9).setFontColor(C_GRAY).setPadding(6));
            } else if (cp != null) {
                DeviceRgb color = probColor(cp);
                t.addCell(new Cell()
                        .add(new Paragraph(String.format("%.0f%%", cp * 100)).setBold().setFontColor(color))
                        .setBorder(new SolidBorder(C_BG_SOFT, 0.5f)).setFontSize(10).setPadding(6));
            } else {
                t.addCell(new Cell().add(new Paragraph("-"))
                        .setBorder(new SolidBorder(C_BG_SOFT, 0.5f)).setFontSize(9).setPadding(6));
            }

            String sourceCell;
            DeviceRgb sourceCellColor;
            if (excluded) {
                sourceCell = "已排除·" + excludeReasonLabel(excludeReason);
                sourceCellColor = C_GRAY;
            } else if (source != null && !"human".equals(source)) {
                sourceCell = "疑似 " + sourceName(source);
                sourceCellColor = sourceColor(source);
            } else {
                sourceCell = "人类";
                sourceCellColor = C_GREEN;
            }
            t.addCell(new Cell().add(new Paragraph(sourceCell).setFontColor(sourceCellColor))
                    .setBorder(new SolidBorder(C_BG_SOFT, 0.5f))
                    .setFontSize(9).setPadding(6));

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
            case "gpt" -> new DeviceRgb(175, 82, 222);
            case "claude" -> new DeviceRgb(255, 45, 85);
            case "deepseek" -> C_PRIMARY;
            case "glm" -> new DeviceRgb(90, 200, 250);
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
}
