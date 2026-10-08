package com.paperaigc.detect.domain.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Map;

/**
 * 账号管理页顶部统计
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AdminAccountStatsVO {
    private long total;
    private long active;
    private long disabled;
    private long todayNew;
    /** 近 7 天有登录 */
    private long active7d;
    private Map<String, Long> byRole;
}
