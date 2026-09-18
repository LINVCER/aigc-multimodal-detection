package com.paperaigc.detect.repository.impl;

import com.paperaigc.detect.common.constant.FeedbackConstants;
import com.paperaigc.detect.domain.entity.Feedback;
import com.paperaigc.detect.repository.IFeedbackRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 反馈仓储 · 内存实现
 *
 * <p>Phase 0 存储；Phase B 会加一个 MybatisFeedbackRepository 走 user_feedback 表，
 * 通过 Spring @Primary / @ConditionalOnProperty 切换。</p>
 */
@Repository
public class InMemoryFeedbackRepository implements IFeedbackRepository {

    private final Map<Long, Feedback> store = new ConcurrentHashMap<>();
    private final AtomicLong idGen = new AtomicLong(1000);

    @Override
    public Feedback save(Feedback f) {
        if (f.getId() == null) f.setId(idGen.incrementAndGet());
        if (f.getCreatedAt() == null) f.setCreatedAt(LocalDateTime.now());
        if (f.getStatus() == null) f.setStatus(FeedbackConstants.STATUS_PENDING);
        store.put(f.getId(), f);
        return f;
    }

    @Override
    public Optional<Feedback> update(Feedback f) {
        if (f.getId() == null || !store.containsKey(f.getId())) return Optional.empty();
        store.put(f.getId(), f);
        return Optional.of(f);
    }

    @Override
    public Optional<Feedback> findById(Long id) {
        return Optional.ofNullable(id == null ? null : store.get(id));
    }

    @Override
    public List<Feedback> findAll() {
        return List.copyOf(store.values());
    }
}
