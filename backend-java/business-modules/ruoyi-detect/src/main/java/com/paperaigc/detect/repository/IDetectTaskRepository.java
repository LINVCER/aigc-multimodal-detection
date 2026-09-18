package com.paperaigc.detect.repository;

import com.paperaigc.detect.domain.entity.DetectTask;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

/**
 * 检测任务存储接口
 *
 * <p>抽象层：当前 InMemoryDetectTaskRepository；Phase B 换 MybatisDetectTaskRepository 走 detect_task 表。</p>
 */
public interface IDetectTaskRepository {

    /** 保存新任务；实现负责生成 id / createdAt */
    DetectTask save(DetectTask task);

    /** 更新已有任务；id 不存在返回 empty */
    Optional<DetectTask> update(DetectTask task);

    /** 按 id 删除；不存在返回 false */
    boolean deleteById(Long id);

    Optional<DetectTask> findById(Long id);

    /** 全量拉取快照，供 Service 做过滤 / 排序 / 分页 */
    Collection<DetectTask> findAll();
}
