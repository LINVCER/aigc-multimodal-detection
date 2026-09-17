-- 企业级论文 AIGC 检测平台 · 初始 Schema
-- 字符集 utf8mb4，排序 utf8mb4_0900_ai_ci
-- 生产环境请改由 Flyway/Liquibase 管理版本化迁移

CREATE DATABASE IF NOT EXISTS paper_aigc DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE paper_aigc;

-- ============ 组织与用户 ============

CREATE TABLE IF NOT EXISTS sys_org (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    code        VARCHAR(64)  NOT NULL UNIQUE,
    name        VARCHAR(128) NOT NULL,
    parent_id   BIGINT       NULL,
    type        VARCHAR(20)  NOT NULL COMMENT 'UNIVERSITY|COLLEGE|DEPARTMENT|CLASS',
    level       INT          NOT NULL DEFAULT 1,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_parent (parent_id)
) COMMENT '组织树';

CREATE TABLE IF NOT EXISTS sys_user (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    org_id      BIGINT       NOT NULL,
    role        VARCHAR(20)  NOT NULL COMMENT 'STUDENT|TEACHER|STAFF|ADMIN',
    username    VARCHAR(64)  NOT NULL UNIQUE,
    password    VARCHAR(100) NOT NULL COMMENT 'BCrypt',
    real_name   VARCHAR(64)  NULL,
    student_no  VARCHAR(32)  NULL,
    email       VARCHAR(128) NULL,
    status      TINYINT      NOT NULL DEFAULT 1 COMMENT '1启用 0停用',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_org (org_id),
    INDEX idx_student_no (student_no)
) COMMENT '用户';

-- ============ 论文与检测 ============

CREATE TABLE IF NOT EXISTS paper (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id     BIGINT       NOT NULL,
    title       VARCHAR(255) NOT NULL,
    degree_type VARCHAR(20)  NOT NULL COMMENT 'BACHELOR|MASTER|PHD',
    file_url    VARCHAR(512) NOT NULL COMMENT 'MinIO 对象路径',
    sha256      CHAR(64)     NOT NULL,
    page_count  INT          NULL,
    word_count  INT          NULL,
    expire_at   DATETIME     NOT NULL COMMENT '原文过期删除时间(上传+30天)',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user (user_id),
    INDEX idx_sha (sha256),
    INDEX idx_expire (expire_at)
) COMMENT '论文';

CREATE TABLE IF NOT EXISTS detect_task (
    id                 BIGINT AUTO_INCREMENT PRIMARY KEY,
    paper_id           BIGINT        NOT NULL,
    status             VARCHAR(16)   NOT NULL DEFAULT 'PENDING' COMMENT 'PENDING|RUNNING|DONE|FAILED',
    ai_rate            DECIMAL(5,2)  NULL COMMENT '文档级 AI 率 0-100',
    source_labels_json JSON          NULL COMMENT '溯源标签分布',
    cost_credit        INT           NOT NULL DEFAULT 0,
    model_version      VARCHAR(64)   NULL,
    created_at         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at        DATETIME      NULL,
    INDEX idx_paper (paper_id),
    INDEX idx_status_created (status, created_at)
) COMMENT '检测任务';

CREATE TABLE IF NOT EXISTS detect_paragraph_result (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id         BIGINT        NOT NULL,
    paragraph_idx   INT           NOT NULL,
    offset_start    INT           NOT NULL,
    offset_end      INT           NOT NULL,
    ai_prob         DECIMAL(6,4)  NULL,
    calibrated_prob DECIMAL(6,4)  NULL,
    source_label    VARCHAR(20)   NULL,
    warnings_json   JSON          NULL,
    INDEX idx_task (task_id)
) COMMENT '段落级检测结果';

CREATE TABLE IF NOT EXISTS detect_sentence_result (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    paragraph_id  BIGINT        NOT NULL,
    sentence_idx  INT           NOT NULL,
    offset_start  INT           NOT NULL,
    offset_end    INT           NOT NULL,
    ai_prob       DECIMAL(6,4)  NULL,
    INDEX idx_paragraph (paragraph_id)
) COMMENT '句子级检测结果';

-- ============ 降 AIGC ============

CREATE TABLE IF NOT EXISTS humanize_task (
    id             BIGINT AUTO_INCREMENT PRIMARY KEY,
    source_task_id BIGINT       NOT NULL COMMENT '来源检测任务',
    original_text  MEDIUMTEXT   NOT NULL,
    rewritten_text MEDIUMTEXT   NULL,
    model_version  VARCHAR(64)  NULL,
    quality_score  DECIMAL(5,2) NULL,
    cost_credit    INT          NOT NULL DEFAULT 0,
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_source (source_task_id)
) COMMENT '降 AIGC 任务';

-- ============ 报告 ============

CREATE TABLE IF NOT EXISTS report (
    id             BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id        BIGINT       NOT NULL,
    pdf_url        VARCHAR(512) NULL,
    excel_url      VARCHAR(512) NULL,
    signed_pdf_url VARCHAR(512) NULL COMMENT '电子签版',
    generated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expire_at      DATETIME     NOT NULL COMMENT '报告保留 3 年',
    INDEX idx_task (task_id)
) COMMENT '检测报告';

-- ============ 计费 ============

CREATE TABLE IF NOT EXISTS credit_account (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    owner_type VARCHAR(10) NOT NULL COMMENT 'ORG|USER',
    owner_id   BIGINT      NOT NULL,
    balance    INT         NOT NULL DEFAULT 0,
    updated_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_owner (owner_type, owner_id)
) COMMENT '额度账户';

CREATE TABLE IF NOT EXISTS credit_transaction (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    account_id BIGINT      NOT NULL,
    delta      INT         NOT NULL COMMENT '正=充值/退款, 负=消耗',
    reason     VARCHAR(20) NOT NULL COMMENT 'RECHARGE|CONSUME|REFUND|GRANT',
    ref_type   VARCHAR(20) NULL COMMENT 'DETECT_TASK|HUMANIZE_TASK|PAYMENT_ORDER',
    ref_id     BIGINT      NULL,
    created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_account_created (account_id, created_at),
    INDEX idx_ref (ref_type, ref_id)
) COMMENT '额度流水(审计对账)';

CREATE TABLE IF NOT EXISTS payment_order (
    id             BIGINT AUTO_INCREMENT PRIMARY KEY,
    account_id     BIGINT        NOT NULL,
    amount         DECIMAL(10,2) NOT NULL,
    method         VARCHAR(16)   NOT NULL COMMENT 'WECHAT|ALIPAY|OFFLINE',
    status         VARCHAR(16)   NOT NULL DEFAULT 'CREATED' COMMENT 'CREATED|PAID|CLOSED|REFUNDED',
    third_party_no VARCHAR(64)   NULL,
    created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_account (account_id)
) COMMENT '支付订单';

-- ============ 审计与模型 ============

CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id     BIGINT       NULL,
    action      VARCHAR(64)  NOT NULL,
    entity_type VARCHAR(32)  NULL,
    entity_id   BIGINT       NULL,
    ip          VARCHAR(45)  NULL,
    ua          VARCHAR(255) NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_created (user_id, created_at)
) COMMENT '审计日志';

CREATE TABLE IF NOT EXISTS model_version (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY,
    name                    VARCHAR(64)  NOT NULL,
    version                 VARCHAR(32)  NOT NULL,
    sha256                  CHAR(64)     NULL,
    calibration_params_json JSON         NULL,
    val_metrics_json        JSON         NULL,
    deployed_at             DATETIME     NULL,
    UNIQUE KEY uk_name_version (name, version)
) COMMENT '模型版本登记';
