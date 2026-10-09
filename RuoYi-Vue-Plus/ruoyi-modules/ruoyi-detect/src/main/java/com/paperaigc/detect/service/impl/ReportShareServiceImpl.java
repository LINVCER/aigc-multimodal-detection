package com.paperaigc.detect.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.paperaigc.detect.common.constant.DetectConstants;
import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import com.paperaigc.detect.domain.dto.CreateShareDTO;
import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.entity.ReportShare;
import com.paperaigc.detect.domain.vo.ReportShareVO;
import com.paperaigc.detect.domain.vo.SharedReportVO;
import com.paperaigc.detect.mapper.ReportShareMapper;
import com.paperaigc.detect.repository.IDetectTaskRepository;
import com.paperaigc.detect.service.IReportShareService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Set;

/**
 * 报告分享实现：token 随机 32 位；view 时计数；URL 由 platform.web.base-url 拼
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ReportShareServiceImpl implements IReportShareService {

    private static final Set<Integer> ALLOWED_DAYS = Set.of(1, 7, 30);
    private static final char[] TOKEN_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789".toCharArray();
    private static final SecureRandom RANDOM = new SecureRandom();
    private static final DateTimeFormatter DAY = DateTimeFormatter.ofPattern("yyyy-MM-dd");

    private final ReportShareMapper shareMapper;
    private final IDetectTaskRepository taskRepository;

    @Value("${platform.web.base-url:http://localhost:5173}")
    private String webBaseUrl;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ReportShareVO create(Long taskId, CreateShareDTO dto, Long ownerUserId) {
        DetectTask task = taskRepository.findById(taskId)
                .orElseThrow(() -> new BizException(ErrorCode.DETECT_TASK_NOT_FOUND));
        if (!DetectConstants.STATUS_DONE.equals(task.getStatus())) {
            throw new BizException(ErrorCode.SHARE_TASK_NOT_DONE);
        }
        int days = dto.getExpireDays() == null ? 7 : dto.getExpireDays();
        if (!ALLOWED_DAYS.contains(days)) throw new BizException(ErrorCode.PARAM_INVALID, "有效期只能是 1 / 7 / 30 天");
        String watermark = dto.getWatermark() == null ? null : dto.getWatermark().trim();

        ReportShare s = ReportShare.builder()
                .token(randomToken())
                .taskId(taskId)
                .ownerUserId(ownerUserId)
                .watermark(watermark == null || watermark.isEmpty() ? null : watermark)
                .expiresAt(LocalDateTime.now().plusDays(days))
                .viewCount(0)
                .revoked(0)
                .createdAt(LocalDateTime.now())
                .build();
        shareMapper.insert(s);
        log.info("report share created: task={} token={} days={}", taskId, s.getToken().substring(0, 6), days);
        return ReportShareVO.from(s, base());
    }

    @Override
    public List<ReportShareVO> list(Long taskId) {
        return shareMapper.selectList(new LambdaQueryWrapper<ReportShare>()
                        .eq(ReportShare::getTaskId, taskId)
                        .orderByDesc(ReportShare::getId))
                .stream().map(s -> ReportShareVO.from(s, base())).toList();
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void revoke(String token) {
        ReportShare s = byToken(token);
        if (s == null) throw new BizException(ErrorCode.SHARE_NOT_FOUND);
        shareMapper.update(null, new LambdaUpdateWrapper<ReportShare>()
                .eq(ReportShare::getId, s.getId()).set(ReportShare::getRevoked, 1));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public SharedReportVO view(String token) {
        ReportShare s = byToken(token);
        if (s == null || (s.getRevoked() != null && s.getRevoked() == 1)) throw new BizException(ErrorCode.SHARE_NOT_FOUND);
        if (s.getExpiresAt() != null && s.getExpiresAt().isBefore(LocalDateTime.now())) throw new BizException(ErrorCode.SHARE_EXPIRED);
        DetectTask task = taskRepository.findById(s.getTaskId())
                .orElseThrow(() -> new BizException(ErrorCode.SHARE_NOT_FOUND));
        shareMapper.update(null, new LambdaUpdateWrapper<ReportShare>()
                .eq(ReportShare::getId, s.getId())
                .setSql("view_count = view_count + 1")
                .set(ReportShare::getLastViewedAt, LocalDateTime.now()));
        s.setViewCount((s.getViewCount() == null ? 0 : s.getViewCount()) + 1);
        String defaultWatermark = "知源 · 只读分享 · " + LocalDateTime.now().format(DAY);
        return SharedReportVO.from(task, s, defaultWatermark);
    }

    private ReportShare byToken(String token) {
        if (token == null || token.length() < 16) return null;
        return shareMapper.selectOne(new LambdaQueryWrapper<ReportShare>().eq(ReportShare::getToken, token));
    }

    private String base() {
        String b = webBaseUrl == null ? "" : webBaseUrl.trim();
        return b.endsWith("/") ? b.substring(0, b.length() - 1) : b;
    }

    private static String randomToken() {
        StringBuilder sb = new StringBuilder(32);
        for (int i = 0; i < 32; i++) sb.append(TOKEN_CHARS[RANDOM.nextInt(TOKEN_CHARS.length)]);
        return sb.toString();
    }
}
