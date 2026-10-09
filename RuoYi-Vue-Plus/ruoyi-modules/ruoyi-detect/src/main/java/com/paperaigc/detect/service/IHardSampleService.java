package com.paperaigc.detect.service;

import com.paperaigc.detect.domain.entity.Feedback;
import com.paperaigc.detect.domain.entity.HardSample;

import java.util.List;

/**
 * 误判样本池（增长闭环 §2.2）
 */
public interface IHardSampleService {

    /**
     * 申诉落库后，把勾选段落写入样本池；未授权只存 hash。同段同模型版本已存在则跳过
     * @param feedback 已保存的申诉（category=appeal，paragraphIdxs 非空）
     * @return 实际新增条数
     */
    int collectFromAppeal(Feedback feedback);

    /**
     * 某条申诉对应的样本
     * @param feedbackId 申诉 id
     * @return 样本列表（按段号）
     */
    List<HardSample> listByFeedback(Long feedbackId);

    /**
     * 运营复核
     * @param sampleId 样本 id
     * @param verdict confirm_fp / confirm_tp / unsure
     * @param reviewer 运营账号 id，可空
     */
    void setVerdict(Long sampleId, String verdict, Long reviewer);

    /**
     * 列表（后台）
     * @param verdict 过滤复核结论，空取全部；"pending" 取未复核
     * @param days 最近 N 天
     * @param limit 上限
     * @return 样本列表
     */
    List<HardSample> list(String verdict, int days, int limit);

    /**
     * 导出评测用样本：已复核且有授权文本的
     * @param verdicts 结论集合
     * @return 样本列表
     */
    List<HardSample> listForExport(List<String> verdicts);
}
