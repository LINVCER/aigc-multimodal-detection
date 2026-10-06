package com.paperaigc.detect.domain.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 运营新增 / 编辑知识块
 */
@Data
public class KnowledgeChunkDTO {

    /** 来源文档名；空则归 ops-faq */
    @Size(max = 64)
    private String doc;

    @NotBlank(message = "标题不能为空")
    @Size(max = 128, message = "标题不能超过 128 字")
    private String title;

    @Size(max = 255)
    private String tags;

    @NotBlank(message = "正文不能为空")
    @Size(max = 20000, message = "正文过长")
    private String body;

    private Integer sortOrder;

    private Boolean enabled;

    /** 从知识缺口「转成知识」时带上来源日志 id，仅审计用 */
    private Long fromLogId;
}
