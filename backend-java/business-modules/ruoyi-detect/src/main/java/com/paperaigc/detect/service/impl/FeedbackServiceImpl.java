package com.paperaigc.detect.service.impl;

import com.paperaigc.detect.common.constant.FeedbackConstants;
import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import com.paperaigc.detect.common.util.ParamUtils;
import com.paperaigc.detect.domain.dto.FeedbackHandleDTO;
import com.paperaigc.detect.domain.dto.FeedbackQueryDTO;
import com.paperaigc.detect.domain.dto.FeedbackSubmitDTO;
import com.paperaigc.detect.domain.entity.Feedback;
import com.paperaigc.detect.domain.vo.FeedbackVO;
import com.paperaigc.detect.domain.vo.PageVO;
import com.paperaigc.detect.repository.IFeedbackRepository;
import com.paperaigc.detect.service.IFeedbackService;
import com.paperaigc.detect.service.IHardSampleService;
import com.paperaigc.detect.service.INotifyService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.List;

/**
 * 用户反馈业务实现
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class FeedbackServiceImpl implements IFeedbackService {

    private final IFeedbackRepository feedbackRepository;
    private final IHardSampleService hardSampleService;
    private final INotifyService notifyService;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Long submit(FeedbackSubmitDTO dto) {
        // 分类校验
        if (!FeedbackConstants.CATEGORIES.contains(dto.getCategory())) {
            throw new BizException(ErrorCode.FEEDBACK_CATEGORY_INVALID);
        }
        // 未登录用户不能提交反馈（W3.c 登录接入前 userId 从请求体透传，为空即未登录）
        if (dto.getUserId() == null) {
            throw new BizException(ErrorCode.UNAUTHORIZED);
        }
        // appeal 必带 taskId
        if (FeedbackConstants.CATEGORY_APPEAL.equals(dto.getCategory()) && dto.getTaskId() == null) {
            throw new BizException(ErrorCode.FEEDBACK_APPEAL_NEED_TASK);
        }

        Feedback fb = Feedback.builder()
                .userId(dto.getUserId())
                .category(dto.getCategory())
                .taskId(dto.getTaskId())
                .paragraphIdxs(dto.getParagraphIdxs() == null || dto.getParagraphIdxs().isEmpty() ? null : dto.getParagraphIdxs())
                .consentImprove(Boolean.TRUE.equals(dto.getConsentImprove()))
                .content(dto.getContent().trim())
                .contact(dto.getContact())
                .status(FeedbackConstants.STATUS_PENDING)
                .build();
        Feedback saved = feedbackRepository.save(fb);

        // 段级申诉进误判样本池（只进评测集；未授权只存哈希）。采样失败不影响申诉本身
        if (FeedbackConstants.CATEGORY_APPEAL.equals(saved.getCategory()) && saved.getParagraphIdxs() != null) {
            try {
                hardSampleService.collectFromAppeal(saved);
            } catch (Exception e) {
                log.warn("hard sample collect failed feedback={}: {}", saved.getId(), e.toString());
            }
        }

        log.info("feedback submitted id={} category={} taskId={}", saved.getId(), saved.getCategory(), saved.getTaskId());
        return saved.getId();
    }

    @Override
    public PageVO<FeedbackVO> page(FeedbackQueryDTO q) {
        List<Feedback> all = feedbackRepository.findAll().stream()
                .filter(f -> ParamUtils.isBlank(q.getStatus()) || q.getStatus().equals(f.getStatus()))
                .filter(f -> q.getUserId() == null || q.getUserId().equals(f.getUserId()))
                .filter(f -> ParamUtils.isBlank(q.getKeyword())
                        || ParamUtils.containsIgnoreCase(f.getContent(), q.getKeyword())
                        || ParamUtils.containsIgnoreCase(f.getContact(), q.getKeyword()))
                .sorted(Comparator.comparing(Feedback::getCreatedAt,
                        Comparator.nullsLast(Comparator.reverseOrder())))
                .toList();

        int total = all.size();
        int pageNum = q.getPageNum() == null || q.getPageNum() < 1 ? 1 : q.getPageNum();
        int pageSize = q.getPageSize() == null || q.getPageSize() < 1 ? 20 : q.getPageSize();
        int from = Math.max(0, (pageNum - 1) * pageSize);
        int to = Math.min(total, from + pageSize);
        List<FeedbackVO> rows = from >= total ? List.of()
                : all.subList(from, to).stream().map(FeedbackVO::from).toList();

        return PageVO.of(total, rows);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void handle(Long id, FeedbackHandleDTO dto) {
        Feedback fb = feedbackRepository.findById(id)
                .orElseThrow(() -> new BizException(ErrorCode.FEEDBACK_NOT_FOUND));

        String newStatus = dto.getStatus();
        if (ParamUtils.isBlank(newStatus) || !FeedbackConstants.STATUSES.contains(newStatus)) {
            newStatus = FeedbackConstants.STATUS_REPLIED;
        }
        String reply = dto.getReply();
        if (FeedbackConstants.STATUS_REPLIED.equals(newStatus) && ParamUtils.isBlank(reply)) {
            throw new BizException(ErrorCode.FEEDBACK_REPLY_EMPTY);
        }

        fb.setStatus(newStatus);
        fb.setHandledBy(dto.getHandledBy());
        fb.setHandledReply(reply);
        fb.setHandledAt(LocalDateTime.now());
        feedbackRepository.update(fb);

        if (FeedbackConstants.STATUS_REPLIED.equals(newStatus) && FeedbackConstants.CATEGORY_APPEAL.equals(fb.getCategory())) {
            try {
                notifyService.appealReplied(fb);
            } catch (Exception e) {
                log.warn("notify appealReplied failed feedback={}: {}", id, e.toString());
            }
        }
    }
}
