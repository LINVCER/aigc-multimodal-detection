package com.paperaigc.detect.domain.vo;

import com.paperaigc.detect.domain.entity.ReportShare;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 分享链接（给报告所有者看）
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ReportShareVO {
    private Long id;
    private String token;
    /** 完整可访问 URL：{platform.web.base-url}/s/{token} */
    private String url;
    private String watermark;
    private LocalDateTime expiresAt;
    private Integer viewCount;
    private Boolean revoked;
    private Boolean expired;
    private LocalDateTime createdAt;

    public static ReportShareVO from(ReportShare s, String baseUrl) {
        boolean expired = s.getExpiresAt() != null && s.getExpiresAt().isBefore(LocalDateTime.now());
        return ReportShareVO.builder()
                .id(s.getId())
                .token(s.getToken())
                .url(baseUrl + "/s/" + s.getToken())
                .watermark(s.getWatermark())
                .expiresAt(s.getExpiresAt())
                .viewCount(s.getViewCount() == null ? 0 : s.getViewCount())
                .revoked(s.getRevoked() != null && s.getRevoked() == 1)
                .expired(expired)
                .createdAt(s.getCreatedAt())
                .build();
    }
}
