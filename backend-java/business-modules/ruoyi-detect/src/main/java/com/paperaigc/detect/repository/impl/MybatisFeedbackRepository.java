package com.paperaigc.detect.repository.impl;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.paperaigc.detect.common.constant.FeedbackConstants;
import com.paperaigc.detect.domain.entity.Feedback;
import com.paperaigc.detect.mapper.FeedbackMapper;
import com.paperaigc.detect.repository.IFeedbackRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Primary;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

/**
 * user_feedback 表 · MyBatis-Plus 实现（Phase B）
 *
 * <p>{@code @Primary} 顶掉同名 InMemory bean；无需切配置就走 DB。
 * InMemory 保留到 Phase B 全 4 batch 跑通后统一删除。</p>
 */
@Primary
@Repository
@RequiredArgsConstructor
public class MybatisFeedbackRepository implements IFeedbackRepository {

    private final FeedbackMapper feedbackMapper;

    @Override
    public Feedback save(Feedback f) {
        // status/createdAt 兜底填充（@TableField(fill=INSERT) 需要 MetaObjectHandler；此处显式赋值双保险）
        if (f.getStatus() == null) f.setStatus(FeedbackConstants.STATUS_PENDING);
        if (f.getCreatedAt() == null) f.setCreatedAt(LocalDateTime.now());
        feedbackMapper.insert(f);
        return f;
    }

    @Override
    public Optional<Feedback> update(Feedback f) {
        if (f.getId() == null) return Optional.empty();
        int n = feedbackMapper.updateById(f);
        return n > 0 ? Optional.of(f) : Optional.empty();
    }

    @Override
    public Optional<Feedback> findById(Long id) {
        return Optional.ofNullable(id == null ? null : feedbackMapper.selectById(id));
    }

    @Override
    public List<Feedback> findAll() {
        // Service 层做过滤/排序/分页；生产量大时把 Query DTO 下推到 SQL 层
        return feedbackMapper.selectList(Wrappers.lambdaQuery(Feedback.class)
                .orderByDesc(Feedback::getCreatedAt));
    }
}
