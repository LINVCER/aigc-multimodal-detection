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
 * 助手知识库分块 —— knowledge_chunk（V0.3.0.002）
 *
 * <p>运营可编辑；推理服务启动 / reload 时全量读 enabled=1 的块进内存 BM25。
 * 字段与 Python assistant/knowledge.py 的 Chunk 对齐：doc › title 即 kb_top_ref。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("knowledge_chunk")
public class KnowledgeChunk {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 来源文档名，如 07-verification；运营新增的统一用 ops-faq */
    private String doc;
    /** 块标题（一句话可搜） */
    private String title;
    /** 文件级标签，逗号分隔 */
    private String tags;
    /** 块正文 */
    private String body;
    /** 同文档内顺序 */
    private Integer sortOrder;
    /** 0 = 下线不参与检索 */
    private Boolean enabled;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
