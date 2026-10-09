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
 * 报告只读分享链接 —— report_share（V0.3.0.011）
 *
 * <p>token 是 32 位随机串，公开页 /s/{token} 凭它读报告；到期或撤销后失效。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("report_share")
public class ReportShare {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String token;
    private Long taskId;
    private Long ownerUserId;
    /** 页面水印文字（可空 → 默认「知源 · 只读分享」） */
    private String watermark;
    private LocalDateTime expiresAt;
    private Integer viewCount;
    /** 1 已撤销 */
    private Integer revoked;
    private LocalDateTime lastViewedAt;
    private LocalDateTime createdAt;
}
