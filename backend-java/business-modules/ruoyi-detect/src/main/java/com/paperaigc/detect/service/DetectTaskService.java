package com.paperaigc.detect.service;

import com.paperaigc.detect.entity.DetectTask;

/**
 * 检测任务编排服务
 *
 * 状态机：PENDING → RUNNING → DONE / FAILED（FAILED 可重试）
 * 流程：抽文本 → 切段切句 → gRPC 批推 → 灰区白盒双检 → 融合 → 报告 → 扣费/退款
 */
public interface DetectTaskService {

    /**
     * 提交论文检测任务（异步执行，虚拟线程池）
     * @param paperId 论文 ID
     * @param userId 提交用户
     * @return 创建的任务
     */
    DetectTask submit(long paperId, long userId);

    /**
     * 查询任务状态与结果
     * @param taskId 任务 ID
     * @return 任务详情
     */
    DetectTask getById(long taskId);

    /**
     * 重试失败任务
     * @param taskId 任务 ID
     * @return 重置后的任务
     */
    DetectTask retry(long taskId);
}
