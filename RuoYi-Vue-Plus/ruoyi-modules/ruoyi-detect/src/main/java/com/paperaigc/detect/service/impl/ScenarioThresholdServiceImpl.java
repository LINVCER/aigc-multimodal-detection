package com.paperaigc.detect.service.impl;

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import com.paperaigc.detect.common.constant.ScenarioConstants;
import com.paperaigc.detect.domain.entity.ScenarioThreshold;
import com.paperaigc.detect.repository.IScenarioThresholdRepository;
import com.paperaigc.detect.service.IScenarioThresholdService;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 场景阈值服务实现（Phase B · Batch 4）
 *
 * <p>Caffeine 本地缓存 5 分钟 · maximumSize 20（6 场景 + 冗余）。</p>
 * <p>DB 空/miss 兜底 {@link ScenarioConstants}，保证 detect 永远能拿到阈值。</p>
 * <p>不引 Spring @Cacheable 抽象层：手工 Cache 更简单可控，避免全局 @EnableCaching 副作用。</p>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ScenarioThresholdServiceImpl implements IScenarioThresholdService {

    private final IScenarioThresholdRepository repository;

    /** scenario → ScenarioThreshold · 5 分钟 TTL；miss 时 loader 走 DB */
    private final Cache<String, ScenarioThreshold> cache = Caffeine.newBuilder()
            .expireAfterWrite(Duration.ofMinutes(5))
            .maximumSize(20)
            .build();

    /** 启动时预热：一次拉全量到缓存，避免首个请求打冷 DB */
    @PostConstruct
    void warmUp() {
        try {
            List<ScenarioThreshold> all = repository.findAllEnabled();
            all.forEach(t -> cache.put(t.getScenario(), t));
            log.info("scenario threshold warm-up: {} rows cached", all.size());
        } catch (Exception e) {
            // 若依基座启动时 DB 未就绪不阻断；后续 threshold() 走兜底
            log.warn("scenario threshold warm-up failed, fallback to ScenarioConstants: {}", e.getMessage());
        }
    }

    @Override
    public int threshold(String scenario) {
        ScenarioThreshold st = get(scenario);
        if (st == null || st.getThreshold() == null) return ScenarioConstants.threshold(scenario);
        return st.getThreshold().setScale(0, RoundingMode.HALF_UP).intValue();
    }

    @Override
    public String label(String scenario) {
        ScenarioThreshold st = get(scenario);
        if (st == null || st.getLabel() == null || st.getLabel().isBlank()) return ScenarioConstants.label(scenario);
        return st.getLabel();
    }

    @Override
    public List<ScenarioThreshold> listAll() {
        return repository.findAllEnabled();
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateThreshold(String scenario, int threshold, boolean enabled) {
        ScenarioThreshold th = ScenarioThreshold.builder()
                .scenario(scenario)
                .threshold(BigDecimal.valueOf(threshold))
                .enabled(enabled ? 1 : 0)
                .updatedAt(LocalDateTime.now())
                .build();
        repository.update(th);
        cache.invalidate(scenario);
        log.info("scenario threshold updated: {}={} enabled={}", scenario, threshold, enabled);
    }

    @Override
    public void invalidateCache() {
        cache.invalidateAll();
        log.info("scenario threshold cache invalidated");
    }

    /** loader：cache miss → DB · null 走兜底 */
    private ScenarioThreshold get(String scenario) {
        if (scenario == null || scenario.isBlank()) return null;
        return cache.get(scenario, k -> repository.findByScenario(k).orElse(null));
    }
}
