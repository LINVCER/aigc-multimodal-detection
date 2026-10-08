package com.paperaigc.detect.service;

import com.paperaigc.detect.domain.dto.DetectTaskQueryDTO;
import com.paperaigc.detect.domain.vo.PageVO;

import java.util.List;
import java.util.Map;

/**
 * 运营后台 · 全平台任务
 */
public interface IAdminTaskService {

    /**
     * SQL 分页列表（运营视图：不带段落，带用户标识）
     * @param query 过滤 / 排序 / 分页
     * @return 行为 Map，字段见实现 maskForAdmin
     */
    PageVO<Map<String, Object>> page(DetectTaskQueryDTO query);

    /**
     * 顶部统计：各状态数 / 今日提交 / 今日失败 / 已完成超线数与占比
     * @return 统计
     */
    Map<String, Object> stats();

    /**
     * 批量删除（走 IDetectTaskService.delete，逐条）
     * @param ids 任务 id
     * @return 成功条数
     */
    int batchDelete(List<Long> ids);

    /**
     * 批量重试，只对 FAILED 生效
     * @param ids 任务 id
     * @return 成功条数
     */
    int batchRetry(List<Long> ids);
}
