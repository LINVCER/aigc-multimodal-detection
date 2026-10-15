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
 * 爬取种子 —— edu_school_crawl_seed（V0.3.0.014）
 *
 * <p>后台「管理爬取的高校」：维护入口页、适配器、开关；定时批量按此刷新（不常驻）。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("edu_school_crawl_seed")
public class EduSchoolCrawlSeed {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long schoolId;
    /** 研究生院 / 教务处通知列表页 */
    private String entryUrl;
    /** adapters/ 里的适配器名 */
    private String adapter;
    /** 1 启用 / 0 停用 */
    private Integer enabled;
    private LocalDateTime lastCrawlAt;
    private String lastStatus;
    private String note;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
