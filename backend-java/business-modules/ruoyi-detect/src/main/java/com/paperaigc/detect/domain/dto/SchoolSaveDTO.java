package com.paperaigc.detect.domain.dto;

import lombok.Data;

/** 新增/编辑学校（手录 50 所走此） */
@Data
public class SchoolSaveDTO {
    private Long id;            // 空=新增
    private String name;
    private String shortName;
    private String aliases;     // JSON 数组文本
    private String province;
    private String level;       // undergrad / vocational / graduate_school
    private String logoUrl;
}
