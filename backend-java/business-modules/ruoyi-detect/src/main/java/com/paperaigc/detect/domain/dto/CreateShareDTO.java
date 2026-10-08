package com.paperaigc.detect.domain.dto;

import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 创建报告分享链接
 */
@Data
public class CreateShareDTO {
    /** 有效期（天）：1 / 7 / 30，缺省 7 */
    private Integer expireDays;

    /** 水印文字，如「仅供张老师审阅」 */
    @Size(max = 40, message = "水印最长 40 字")
    private String watermark;
}
