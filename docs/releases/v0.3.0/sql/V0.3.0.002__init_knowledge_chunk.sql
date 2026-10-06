-- ============================================================
-- V0.3.0.002 · 论文检测助手知识库分块表
-- 对齐 deploy/inference-python/assistant/knowledge.py 的 Chunk 结构
-- 设计见 docs/design/202610-knowledge-base-retrieval-plan.md（Phase 1）
-- 幂等：CREATE TABLE IF NOT EXISTS
-- ============================================================

CREATE TABLE IF NOT EXISTS knowledge_chunk (
  id           BIGINT PRIMARY KEY AUTO_INCREMENT,
  doc          VARCHAR(64)  NOT NULL COMMENT '来源文档，如 07-verification',
  title        VARCHAR(128) NOT NULL COMMENT '块标题（## 二级标题）',
  tags         VARCHAR(255) DEFAULT '' COMMENT '文件级标签，逗号分隔',
  body         TEXT         NOT NULL COMMENT '块正文',
  sort_order   INT          NOT NULL DEFAULT 0 COMMENT '同文档内顺序',
  enabled      TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '运营可下线某块（0=下线不参与检索）',
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_doc_title (doc, title),
  INDEX idx_doc (doc),
  INDEX idx_enabled (enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '助手知识库分块（运营可编辑，推理服务启动时全量加载进内存 BM25）';
