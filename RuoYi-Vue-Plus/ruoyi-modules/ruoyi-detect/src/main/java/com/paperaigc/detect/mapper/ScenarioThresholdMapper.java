package com.paperaigc.detect.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.paperaigc.detect.domain.entity.ScenarioThreshold;
import org.apache.ibatis.annotations.Mapper;

/**
 * detect_scenario_threshold 表 Mapper
 *
 * <p>数据量固定 6 行；Repository 层 findAll 即可覆盖全部业务。</p>
 */
@Mapper
public interface ScenarioThresholdMapper extends BaseMapper<ScenarioThreshold> {
}
