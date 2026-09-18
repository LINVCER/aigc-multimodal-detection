package com.paperaigc.detect.repository.impl;

import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.repository.IDetectTaskRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 检测任务 · 内存仓储
 *
 * <p>Phase 0 存储；Phase B 换 MybatisDetectTaskRepository 走 detect_task 表。</p>
 */
@Repository
public class InMemoryDetectTaskRepository implements IDetectTaskRepository {

    private final Map<Long, DetectTask> store = new ConcurrentHashMap<>();
    private final AtomicLong idGen = new AtomicLong(1000);

    @Override
    public DetectTask save(DetectTask t) {
        if (t.getId() == null) t.setId(idGen.incrementAndGet());
        if (t.getCreatedAt() == null) t.setCreatedAt(LocalDateTime.now());
        store.put(t.getId(), t);
        return t;
    }

    @Override
    public Optional<DetectTask> update(DetectTask t) {
        if (t.getId() == null || !store.containsKey(t.getId())) return Optional.empty();
        store.put(t.getId(), t);
        return Optional.of(t);
    }

    @Override
    public boolean deleteById(Long id) {
        return id != null && store.remove(id) != null;
    }

    @Override
    public Optional<DetectTask> findById(Long id) {
        return Optional.ofNullable(id == null ? null : store.get(id));
    }

    @Override
    public Collection<DetectTask> findAll() {
        return store.values();
    }
}
