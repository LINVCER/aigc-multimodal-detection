package com.paperaigc.detect.repository;

import com.paperaigc.detect.domain.entity.ScenarioThreshold;

import java.util.List;
import java.util.Optional;

/**
 * 场景阈值仓储
 */
public interface IScenarioThresholdRepository {

    Optional<ScenarioThreshold> findByScenario(String scenario);

    /** 全量启用配置（enabled=1） */
    List<ScenarioThreshold> findAllEnabled();

    /** 运营后台改阈值 · 返回是否成功 */
    boolean update(ScenarioThreshold th);
}
