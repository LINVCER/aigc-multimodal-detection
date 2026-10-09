package com.paperaigc.detect.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.paperaigc.detect.common.constant.DetectConstants;
import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.entity.ParagraphResult;
import com.paperaigc.detect.domain.vo.ReportVerifyVO;
import com.paperaigc.detect.mapper.DetectTaskMapper;
import com.paperaigc.detect.repository.IDetectTaskRepository;
import com.paperaigc.detect.service.IReportCredentialService;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;

/**
 * 报告凭证实现
 *
 * <p>编号格式 ZY-yyyyMMdd-XXXXXX（6 位去易混字符），验证码 8 位；签名密钥来自 platform.report.sign-secret。</p>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ReportCredentialServiceImpl implements IReportCredentialService {

    private static final String DEFAULT_SECRET = "zhiyuan-dev-secret-change-me";
    private static final char[] CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789".toCharArray();
    private static final SecureRandom RANDOM = new SecureRandom();
    private static final DateTimeFormatter DAY = DateTimeFormatter.ofPattern("yyyyMMdd");

    private final DetectTaskMapper taskMapper;
    private final IDetectTaskRepository taskRepository;

    @Value("${platform.report.sign-secret:" + DEFAULT_SECRET + "}")
    private String secret;

    @Value("${platform.web.base-url:http://localhost:5173}")
    private String webBaseUrl;

    @PostConstruct
    void warnDefaultSecret() {
        if (DEFAULT_SECRET.equals(secret)) {
            log.warn("platform.report.sign-secret 使用默认值，生产环境必须通过 REPORT_SIGN_SECRET 覆盖，否则报告签名可被伪造");
        }
    }

    @Override
    public DetectTask ensure(DetectTask task) {
        if (task == null || !DetectConstants.STATUS_DONE.equals(task.getStatus())) return task;
        boolean signed = task.getReportNo() != null && !task.getReportNo().isBlank() && task.getReportSign() != null;
        // 重试后 finishedAt 晚于 signedAt：结果变了，保留编号与验证码，重新签名
        boolean stale = signed && task.getFinishedAt() != null && task.getSignedAt() != null && task.getFinishedAt().isAfter(task.getSignedAt());
        if (signed && !stale) return task;

        if (task.getParagraphs() == null) {
            // 调用方只带了列表字段：重新读一遍带段落的完整任务，签名才覆盖段落结果
            DetectTask full = taskRepository.findById(task.getId()).orElse(null);
            if (full != null) task.setParagraphs(full.getParagraphs());
        }
        String reportNo = task.getReportNo();
        if (reportNo == null || reportNo.isBlank()) {
            for (int i = 0; i < 5; i++) {
                String candidate = "ZY-" + LocalDateTime.now().format(DAY) + "-" + random(6);
                if (taskMapper.selectCount(new LambdaQueryWrapper<DetectTask>().eq(DetectTask::getReportNo, candidate)) == 0) {
                    reportNo = candidate;
                    break;
                }
            }
            if (reportNo == null) throw new IllegalStateException("报告编号生成失败");
        }
        String code = task.getVerifyCode() == null || task.getVerifyCode().isBlank() ? random(8) : task.getVerifyCode();
        LocalDateTime signedAt = LocalDateTime.now();
        task.setReportNo(reportNo);
        task.setVerifyCode(code);
        task.setSignedAt(signedAt);
        task.setReportSign(sign(task));
        taskMapper.update(null, new LambdaUpdateWrapper<DetectTask>()
                .eq(DetectTask::getId, task.getId())
                .set(DetectTask::getReportNo, reportNo)
                .set(DetectTask::getVerifyCode, code)
                .set(DetectTask::getReportSign, task.getReportSign())
                .set(DetectTask::getSignedAt, signedAt));
        log.info("report credential issued task={} reportNo={}", task.getId(), reportNo);
        return task;
    }

    @Override
    public ReportVerifyVO verify(String reportNo, String code) {
        String no = reportNo == null ? "" : reportNo.trim().toUpperCase(Locale.ROOT);
        String c = code == null ? "" : code.trim().toUpperCase(Locale.ROOT);
        if (no.isEmpty() || c.isEmpty()) return ReportVerifyVO.invalid("请输入报告编号和验证码");
        DetectTask brief = taskMapper.selectOne(new LambdaQueryWrapper<DetectTask>().eq(DetectTask::getReportNo, no));
        if (brief == null || brief.getVerifyCode() == null || !brief.getVerifyCode().equalsIgnoreCase(c)) {
            // 编号不存在与验证码错误给同一句，避免被用来探测编号
            return ReportVerifyVO.invalid("报告编号或验证码不正确");
        }
        DetectTask task = taskRepository.findById(brief.getId()).orElse(brief);
        boolean signatureValid = task.getReportSign() != null && task.getReportSign().equals(sign(task));
        taskMapper.update(null, new LambdaUpdateWrapper<DetectTask>()
                .eq(DetectTask::getId, task.getId()).setSql("verify_count = IFNULL(verify_count, 0) + 1"));
        int count = (task.getVerifyCount() == null ? 0 : task.getVerifyCount()) + 1;
        return ReportVerifyVO.of(task, signatureValid, fingerprint(task), count);
    }

    @Override
    public String fingerprint(DetectTask task) {
        String s = task == null ? null : task.getReportSign();
        return s == null || s.length() < 16 ? null : s.substring(0, 16).toUpperCase(Locale.ROOT);
    }

    @Override
    public String verifyUrl(DetectTask task) {
        if (task == null || task.getReportNo() == null) return null;
        String b = webBaseUrl == null ? "" : webBaseUrl.trim();
        if (b.endsWith("/")) b = b.substring(0, b.length() - 1);
        return b + "/verify/" + task.getReportNo() + "?code=" + task.getVerifyCode();
    }

    /* ==================== helpers ==================== */

    /** 签名覆盖：编号 | 任务 id | AI 率 | 红线 | 场景 | 模型 | 完成时间（秒级，DATETIME 不存毫秒）| 字数 | 段落摘要 */
    private String sign(DetectTask t) {
        String canonical = String.join("|",
                nz(t.getReportNo()), nz(t.getId()), nz(t.getAiRate()), nz(t.getThreshold()), nz(t.getScenario()),
                nz(t.getModelVersion()), t.getFinishedAt() == null ? "" : t.getFinishedAt().withNano(0).toString(), nz(t.getWordCount()), paragraphDigest(t.getParagraphs()));
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            return hex(mac.doFinal(canonical.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            throw new IllegalStateException("HMAC-SHA256 不可用", e);
        }
    }

    /** 段落结果摘要：按序号排序后 "idx:校准概率:是否排除" 拼接再 SHA-256，段落文本不进摘要（避免大文本） */
    private static String paragraphDigest(List<ParagraphResult> paragraphs) {
        if (paragraphs == null || paragraphs.isEmpty()) return "-";
        StringBuilder sb = new StringBuilder();
        paragraphs.stream().sorted(Comparator.comparing(p -> p.getParagraphIdx() == null ? -1 : p.getParagraphIdx())).forEach(p ->
                sb.append(p.getParagraphIdx()).append(':').append(p.getCalibratedProb() == null ? "" : String.format(Locale.ROOT, "%.4f", p.getCalibratedProb()))
                        .append(':').append(p.isExcluded() ? 1 : 0).append(';'));
        try {
            return hex(MessageDigest.getInstance("SHA-256").digest(sb.toString().getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            throw new IllegalStateException("SHA-256 不可用", e);
        }
    }

    private static String nz(Object o) { return o == null ? "" : String.valueOf(o); }

    private static String hex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) sb.append(String.format(Locale.ROOT, "%02x", b));
        return sb.toString();
    }

    private static String random(int n) {
        StringBuilder sb = new StringBuilder(n);
        for (int i = 0; i < n; i++) sb.append(CODE_CHARS[RANDOM.nextInt(CODE_CHARS.length)]);
        return sb.toString();
    }
}
