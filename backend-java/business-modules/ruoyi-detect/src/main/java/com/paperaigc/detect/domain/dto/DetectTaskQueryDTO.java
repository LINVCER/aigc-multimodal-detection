package com.paperaigc.detect.domain.dto;

import lombok.Data;

/**
 * 任务列表查询条件（C 端 §3.2 & 运营 §3.4 共用）
 */
@Data
public class DetectTaskQueryDTO {

    /** 状态过滤：PENDING/RUNNING/DONE/FAILED；空为不限 */
    private String status;

    /** AI 率分桶：0-10 / 10-20 / 20-30 / 30-50 / 50-100（与 DetectAnalyticsServiceImpl.bucketOf 同口径） */
    private String rateBucket;
    /** 达标：true = ai_rate ≤ threshold；false = 超线；空不限 */
    private Boolean pass;
    /** 模型版本精确匹配 */
    private String modelVersion;
    /** 创建日期区间（含），yyyy-MM-dd */
    private String dateFrom;
    private String dateTo;
    /** 场景过滤（后台专用） */
    private String scenario;
    /** 关键字：paperTitle 大小写不敏感 contains */
    private String keyword;
    /** C 端"我的任务"用；后台不传 */
    private Long userId;

    /** AI 率区间（后台专用） */
    private Double minAiRate;
    private Double maxAiRate;

    /** 排序白名单：createdAt / aiRate / wordCount；缺省 id 倒序 */
    private String sortBy;
    /** asc / desc */
    private String sortOrder;

    private Integer pageNum = 1;
    private Integer pageSize = 20;
}
