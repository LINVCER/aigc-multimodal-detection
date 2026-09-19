package com.paperaigc.detect.repository.impl;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.paperaigc.detect.domain.entity.ScenarioThreshold;
import com.paperaigc.detect.mapper.ScenarioThresholdMapper;
import com.paperaigc.detect.repository.IScenarioThresholdRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Primary;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * detect_scenario_threshold 表 · MyBatis-Plus 实现（Phase B · Batch 4）
 *
 * <p>无 InMemory 对应实现（原本走 ScenarioConstants 硬编码常量，作 Service 兜底不作 Repository）。
 * 数据量固定 6 行，全量查询走 findAllEnabled 一次拉入 Service 侧 Caffeine 缓存。</p>
 */
@Primary
@Repository
@RequiredArgsConstructor
public class MybatisScenarioThresholdRepository implements IScenarioThresholdRepository {

    private final ScenarioThresholdMapper mapper;

    @Override
    public Optional<ScenarioThreshold> findByScenario(String scenario) {
        if (scenario == null || scenario.isBlank()) return Optional.empty();
        return Optional.ofNullable(mapper.selectById(scenario));
    }

    @Override
    public List<ScenarioThreshold> findAllEnabled() {
        return mapper.selectList(Wrappers.lambdaQuery(ScenarioThreshold.class)
                .eq(ScenarioThreshold::getEnabled, 1));
    }

    @Override
    public boolean update(ScenarioThreshold th) {
        if (th == null || th.getScenario() == null) return false;
        return mapper.updateById(th) > 0;
    }
}
