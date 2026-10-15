package com.paperaigc.detect.domain.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/** 学校搜索结果项 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SchoolVO {
    private Long id;
    private String name;
    private String shortName;
    private String province;
    private String level;
}
