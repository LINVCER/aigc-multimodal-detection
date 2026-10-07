package com.paperaigc.detect.service;

import com.paperaigc.detect.domain.vo.TaskCompareVO;

/**
 * 复测对比（product-feature-plan §2.2）
 */
public interface ITaskCompareService {

    /**
     * 当前任务与其 parent_task_id 的段级对比
     * @param taskId 当前任务（修改稿）
     * @return 对比视图；任务无 parent 时抛 DETECT_TASK_NOT_FOUND 的变体 PARAM_INVALID
     */
    TaskCompareVO compare(Long taskId);
}
