-- ============================================================
-- V0.3.0.014 · 学校红线：学校表 / 已发布规则 / 爬虫候选 / 爬取种子
-- 对齐 docs/design/202610-school-redline-plan.md §2、§11
-- 幂等：表用 CREATE TABLE IF NOT EXISTS；auth_user / detect_task 增列用 information_schema 检查
-- 数据变更只归档，不代跑；执行方按 migration 规范上。
-- ============================================================

-- 1. 学校表（教育部高校名单一次性导入；aliases 容「北航/北京航空航天大学」）
CREATE TABLE IF NOT EXISTS edu_school (
  id          BIGINT PRIMARY KEY AUTO_INCREMENT,
  name        VARCHAR(128) NOT NULL COMMENT '全称',
  short_name  VARCHAR(32)  NULL COMMENT '短名',
  aliases     JSON         NULL COMMENT '别名数组，如 ["北航","BUAA"]',
  province    VARCHAR(32)  NULL COMMENT '省份',
  level       VARCHAR(16)  NOT NULL DEFAULT 'undergrad' COMMENT 'undergrad / vocational / graduate_school',
  logo_url    VARCHAR(256) NULL,
  status      VARCHAR(16)  NOT NULL DEFAULT 'active' COMMENT 'active / hidden',
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_name (name),
  KEY idx_province (province)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '高校';

-- 2. 已发布红线规则（人工审核后的干净数据；一行=一个 学校+学院+学位 的红线）
CREATE TABLE IF NOT EXISTS edu_school_rule (
  id               BIGINT PRIMARY KEY AUTO_INCREMENT,
  school_id        BIGINT       NOT NULL,
  college          VARCHAR(64)  NULL COMMENT '学院，NULL=全校',
  degree_type      VARCHAR(16)  NOT NULL COMMENT 'bachelor / master / phd',
  ai_rate_limit    DECIMAL(5,2) NULL COMMENT 'AIGC 率红线 %',
  plagiarism_limit DECIMAL(5,2) NULL COMMENT '查重率红线 %',
  platform         VARCHAR(32)  NULL COMMENT 'cnki / vip / wanfang / gezida / other',
  source_type      VARCHAR(16)  NOT NULL DEFAULT 'official' COMMENT 'official / user / inferred',
  source_url       VARCHAR(512) NULL,
  effective_year   SMALLINT     NULL COMMENT '适用届别',
  confidence       TINYINT      NOT NULL DEFAULT 100,
  status           VARCHAR(16)  NOT NULL DEFAULT 'published' COMMENT 'published / stale / rejected',
  verified_by      BIGINT       NULL,
  verified_at      DATETIME     NULL,
  created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_resolve (school_id, degree_type, status),
  KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '高校学位论文红线（已发布）';

-- 3. 爬虫候选（highschool-spider 产出的原始 per-metric 行，噪声大，供后台审核合并进 edu_school_rule）
CREATE TABLE IF NOT EXISTS edu_school_rule_candidate (
  id             BIGINT PRIMARY KEY AUTO_INCREMENT,
  school_id      BIGINT       NULL COMMENT '可空：爬虫按种子带入，无法对应时为 NULL 待人工认领',
  school_name    VARCHAR(128) NULL,
  degree_type    VARCHAR(16)  NOT NULL DEFAULT 'unknown' COMMENT 'bachelor/master/phd/unknown',
  metric         VARCHAR(16)  NOT NULL COMMENT 'ai_rate / plagiarism',
  limit_pct      DECIMAL(5,2) NOT NULL,
  platform       VARCHAR(32)  NULL,
  effective_year SMALLINT     NULL,
  snippet        VARCHAR(255) NULL COMMENT '原文片段，供人工核对',
  source_url     VARCHAR(512) NOT NULL,
  confidence     TINYINT      NOT NULL DEFAULT 0,
  content_hash   CHAR(40)     NOT NULL COMMENT '去重：sha1(school_id|degree|metric|pct|source_url)',
  status         VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT 'pending / merged / rejected',
  merged_rule_id BIGINT       NULL COMMENT '合并后指向 edu_school_rule.id',
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_hash (content_hash),
  KEY idx_status (status, confidence),
  KEY idx_school (school_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '高校红线爬虫候选（审核队列）';

-- 4. 爬取种子（后台「管理爬取的高校」：维护入口页、适配器、开关、上次爬取时间）
CREATE TABLE IF NOT EXISTS edu_school_crawl_seed (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  school_id     BIGINT       NOT NULL,
  entry_url     VARCHAR(512) NOT NULL COMMENT '研究生院/教务处通知列表页',
  adapter       VARCHAR(32)  NOT NULL DEFAULT 'generic' COMMENT 'adapters/ 里的适配器名',
  enabled       TINYINT(1)   NOT NULL DEFAULT 1,
  last_crawl_at DATETIME     NULL,
  last_status   VARCHAR(255) NULL COMMENT '上次爬取结果简述（抓N页/候选M条/错误）',
  note          VARCHAR(255) NULL,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_school_entry (school_id, entry_url)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '高校爬取种子';

-- 5. auth_user 增列：用户所属学校与学位（报告红线按校解析）
SET @c1 := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'auth_user' AND COLUMN_NAME = 'school_id');
SET @sql := IF(@c1 = 0,
  'ALTER TABLE auth_user ADD COLUMN school_id BIGINT NULL COMMENT ''所属高校 edu_school.id'' AFTER org_name',
  'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @c2 := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'auth_user' AND COLUMN_NAME = 'degree_type');
SET @sql := IF(@c2 = 0,
  'ALTER TABLE auth_user ADD COLUMN degree_type VARCHAR(16) NULL COMMENT ''bachelor / master / phd'' AFTER school_id',
  'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- 6. detect_task 增列：记录当次任务用的红线规则，规则日后改动不影响历史报告解释
SET @c3 := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'detect_task' AND COLUMN_NAME = 'school_rule_id');
SET @sql := IF(@c3 = 0,
  'ALTER TABLE detect_task ADD COLUMN school_rule_id BIGINT NULL COMMENT ''当次生效的 edu_school_rule.id'' AFTER scenario',
  'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @c4 := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'detect_task' AND COLUMN_NAME = 'rule_label');
SET @sql := IF(@c4 = 0,
  'ALTER TABLE detect_task ADD COLUMN rule_label VARCHAR(64) NULL COMMENT ''红线来源标签，如「北航·硕士」/「通用标准」'' AFTER school_rule_id',
  'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
