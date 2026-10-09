package com.paperaigc.detect.repository;

import com.paperaigc.detect.domain.entity.Feedback;

import java.util.List;
import java.util.Optional;

/**
 * 反馈存储接口
 *
 * <p>抽象层：Phase B 起走 {@code MybatisFeedbackRepository} → user_feedback 表。
 * Controller / Service 不感知底层；未来切 Redis / 缓存层加一份 impl 即可。</p>
 */
public interface IFeedbackRepository {

    /**
     * 保存新反馈；实现负责生成 id / createdAt
     * @param feedback 未持久化的反馈实例（id 可为空）
     * @return 已带 id 的反馈实例
     */
    Feedback save(Feedback feedback);

    /**
     * 更新已有反馈（处理状态 / 回复 / 处理人 / 时间）
     * @param feedback 带 id 的反馈实例
     * @return 更新后的实例；id 不存在返回 empty
     */
    Optional<Feedback> update(Feedback feedback);

    /**
     * 按 id 查找
     * @param id 反馈 id
     * @return Optional 包装
     */
    Optional<Feedback> findById(Long id);

    /**
     * 全量拉取（供 Service 做过滤 / 排序 / 分页）
     * <p>本地内存 OK；DB 实现应在此下推 SQL 过滤，此方法保留兜底。</p>
     */
    List<Feedback> findAll();
}
