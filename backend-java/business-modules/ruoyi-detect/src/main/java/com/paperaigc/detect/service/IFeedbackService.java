package com.paperaigc.detect.service;

import com.paperaigc.detect.domain.dto.FeedbackHandleDTO;
import com.paperaigc.detect.domain.dto.FeedbackQueryDTO;
import com.paperaigc.detect.domain.dto.FeedbackSubmitDTO;
import com.paperaigc.detect.domain.vo.FeedbackVO;
import com.paperaigc.detect.domain.vo.PageVO;

/**
 * 用户反馈业务接口（W3.d）
 */
public interface IFeedbackService {

    /**
     * C 端提交反馈
     * @param dto 请求参数
     * @return 新建反馈 id
     */
    Long submit(FeedbackSubmitDTO dto);

    /**
     * 分页查询反馈列表（C 端 mine + 后台通用）
     * @param query 查询条件
     * @return 分页 VO
     */
    PageVO<FeedbackVO> page(FeedbackQueryDTO query);

    /**
     * 运营处理反馈（写回复 + 变更状态）
     * @param id 反馈 id
     * @param dto 处理参数
     */
    void handle(Long id, FeedbackHandleDTO dto);

    /**
     * 后台统计：按状态 / 按分类 / 今日新增 / 待处理申诉数
     * @return 统计 Map
     */
    java.util.Map<String, Object> stats();

    /**
     * 批量处置（忽略 / 置处理中 / 统一回复）
     * @param ids 反馈 id
     * @param dto 状态 / 回复
     * @return 成功条数
     */
    int batchHandle(java.util.List<Long> ids, FeedbackHandleDTO dto);
}
