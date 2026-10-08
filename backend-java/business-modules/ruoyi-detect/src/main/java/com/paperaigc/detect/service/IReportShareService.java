package com.paperaigc.detect.service;

import com.paperaigc.detect.domain.dto.CreateShareDTO;
import com.paperaigc.detect.domain.vo.ReportShareVO;
import com.paperaigc.detect.domain.vo.SharedReportVO;

import java.util.List;

/**
 * 报告只读分享链接
 */
public interface IReportShareService {

    /**
     * 创建分享链接（任务须已完成）
     * @param taskId 任务 id
     * @param dto 有效期 / 水印
     * @param ownerUserId 创建者（可空）
     * @return 链接信息，含完整 URL
     */
    ReportShareVO create(Long taskId, CreateShareDTO dto, Long ownerUserId);

    /**
     * 某任务的全部分享链接（含已撤销 / 已过期，前端区分展示）
     * @param taskId 任务 id
     * @return 按创建时间倒序
     */
    List<ReportShareVO> list(Long taskId);

    /**
     * 撤销链接
     * @param token 分享 token
     */
    void revoke(String token);

    /**
     * 公开读取：校验撤销 / 过期，计一次浏览
     * @param token 分享 token
     * @return 只读报告
     */
    SharedReportVO view(String token);
}
