package com.paperaigc.detect.domain.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/** 学校详情 + 已发布红线（公开查询页 /schools/{id}） */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SchoolDetailVO {
    private Long id;
    private String name;
    private String shortName;
    private String province;
    private String level;
    private List<SchoolRuleVO> rules;
}
