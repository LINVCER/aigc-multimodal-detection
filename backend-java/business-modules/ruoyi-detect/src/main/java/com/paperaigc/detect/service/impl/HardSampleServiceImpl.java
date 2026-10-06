package com.paperaigc.detect.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.entity.Feedback;
import com.paperaigc.detect.domain.entity.HardSample;
import com.paperaigc.detect.domain.entity.ParagraphResult;
import com.paperaigc.detect.mapper.DetectParagraphResultMapper;
import com.paperaigc.detect.mapper.HardSampleMapper;
import com.paperaigc.detect.repository.IDetectTaskRepository;
import com.paperaigc.detect.service.IHardSampleService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDateTime;
import java.util.HexFormat;
import java.util.List;
import java.util.Set;

/**
 * 误判样本池实现
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class HardSampleServiceImpl implements IHardSampleService {

    private static final Set<String> VERDICTS = Set.of(
            HardSample.VERDICT_CONFIRM_FP, HardSample.VERDICT_CONFIRM_TP, HardSample.VERDICT_UNSURE);

    private final HardSampleMapper sampleMapper;
    private final DetectParagraphResultMapper paragraphMapper;
    private final IDetectTaskRepository taskRepository;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public int collectFromAppeal(Feedback fb) {
        if (fb.getTaskId() == null || fb.getParagraphIdxs() == null || fb.getParagraphIdxs().isEmpty()) return 0;
        DetectTask task = taskRepository.findById(fb.getTaskId()).orElse(null);
        if (task == null) return 0;
        String version = task.getModelVersion() == null ? "unknown" : task.getModelVersion();
        boolean consent = Boolean.TRUE.equals(fb.getConsentImprove());

        List<ParagraphResult> paras = paragraphMapper.selectList(new LambdaQueryWrapper<ParagraphResult>()
                .eq(ParagraphResult::getTaskId, fb.getTaskId())
                .in(ParagraphResult::getParagraphIdx, fb.getParagraphIdxs()));
        int added = 0;
        for (ParagraphResult p : paras) {
            if (p.getText() == null || p.getText().isBlank()) continue;
            String hash = sha256(p.getText());
            Long dup = sampleMapper.selectCount(new LambdaQueryWrapper<HardSample>()
                    .eq(HardSample::getTextSha256, hash).eq(HardSample::getModelVersion, version));
            if (dup != null && dup > 0) continue;
            HardSample s = HardSample.builder()
                    .feedbackId(fb.getId()).taskId(fb.getTaskId()).paragraphIdx(p.getParagraphIdx())
                    .textSha256(hash)
                    .text(consent ? p.getText() : null)
                    .modelProb(p.getCalibratedProb() == null ? null : BigDecimal.valueOf(p.getCalibratedProb()))
                    .modelVersion(version)
                    .userLabel("human")
                    .source("appeal")
                    .scenario(task.getScenario())
                    .createdAt(LocalDateTime.now())
                    .build();
            sampleMapper.insert(s);
            added++;
        }
        log.info("hard sample collected feedback={} task={} added={} consent={}", fb.getId(), fb.getTaskId(), added, consent);
        return added;
    }

    @Override
    public List<HardSample> listByFeedback(Long feedbackId) {
        return sampleMapper.selectList(new LambdaQueryWrapper<HardSample>()
                .eq(HardSample::getFeedbackId, feedbackId).orderByAsc(HardSample::getParagraphIdx));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void setVerdict(Long sampleId, String verdict, Long reviewer) {
        if (verdict == null || !VERDICTS.contains(verdict)) {
            throw new BizException(ErrorCode.PARAM_INVALID, "verdict 必须是 confirm_fp / confirm_tp / unsure");
        }
        HardSample s = sampleMapper.selectById(sampleId);
        if (s == null) throw new BizException(ErrorCode.NOT_FOUND);
        s.setOpsVerdict(verdict);
        s.setReviewedBy(reviewer);
        s.setReviewedAt(LocalDateTime.now());
        sampleMapper.updateById(s);
    }

    @Override
    public List<HardSample> list(String verdict, int days, int limit) {
        LambdaQueryWrapper<HardSample> qw = new LambdaQueryWrapper<HardSample>()
                .ge(HardSample::getCreatedAt, LocalDateTime.now().minusDays(Math.max(days, 1)));
        if ("pending".equals(verdict)) qw.isNull(HardSample::getOpsVerdict);
        else if (verdict != null && !verdict.isBlank()) qw.eq(HardSample::getOpsVerdict, verdict);
        qw.orderByDesc(HardSample::getCreatedAt).last("LIMIT " + Math.min(Math.max(limit, 1), 1000));
        return sampleMapper.selectList(qw);
    }

    @Override
    public List<HardSample> listForExport(List<String> verdicts) {
        return sampleMapper.selectList(new LambdaQueryWrapper<HardSample>()
                .in(HardSample::getOpsVerdict, verdicts)
                .isNotNull(HardSample::getText)
                .orderByAsc(HardSample::getId));
    }

    private static String sha256(String s) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(md.digest(s.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }
}
