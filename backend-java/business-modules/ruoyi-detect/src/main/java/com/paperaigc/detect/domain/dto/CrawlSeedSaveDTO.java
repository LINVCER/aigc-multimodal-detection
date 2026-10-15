package com.paperaigc.detect.domain.dto;

import lombok.Data;

/** 新增/编辑爬取种子 */
@Data
public class CrawlSeedSaveDTO {
    private Long id;            // 空=新增
    private Long schoolId;
    private String entryUrl;
    private String adapter;     // 默认 generic
    private Integer enabled;    // 1/0
    private String note;
}
