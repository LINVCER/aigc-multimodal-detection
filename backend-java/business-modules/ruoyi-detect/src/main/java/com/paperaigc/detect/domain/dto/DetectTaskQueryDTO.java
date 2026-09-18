package com.paperaigc.detect.domain.dto;

import lombok.Data;

/**
 * 任务列表查询条件（C 端 §3.2 & 运营 §3.4 共用）
 */
@Data
public class DetectTaskQueryDTO {

    /** 状态过滤：PENDING/RUNNING/DONE/FAILED；空为不限 */
    private String status;
    /** 场景过滤（后台专用） */
    private String scenario;
    /** 关键字：paperTitle 大小写不敏感 contains */
    private String keyword;
    /** C 端"我的任务"用；后台不传 */
    private Long userId;

    /** AI 率区间（后台专用） */
    private Double minAiRate;
    private Double maxAiRate;

    private Integer pageNum = 1;
    private Integer pageSize = 20;
}
