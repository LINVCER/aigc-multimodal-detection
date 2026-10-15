package com.paperaigc.detect.domain.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 高校 —— edu_school（V0.3.0.014）
 *
 * <p>aliases 为 JSON 数组文本（如 ["北航","BUAA"]），搜索按 LIKE 命中，不做 JSON typeHandler。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("edu_school")
public class EduSchool {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 全称，唯一 */
    private String name;
    private String shortName;
    /** 别名 JSON 数组文本 */
    private String aliases;
    private String province;
    /** undergrad / vocational / graduate_school */
    private String level;
    private String logoUrl;
    /** active / hidden */
    private String status;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
