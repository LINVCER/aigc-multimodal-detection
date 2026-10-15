"""
站点适配器基类 + 通用适配器
============================

借 spider-v2 的 platforms/<name>/ 思路：每所页面结构特殊的学校可写一个子类覆盖，
大多数学校走 GenericAdapter（关键词驱动）即可。调度器按注册表选第一个 match 的，兜底用 generic。
"""
from __future__ import annotations

import extract

# 链接是否值得跟进：锚文本或 URL 命中这些词才入队，避免把整站爬一遍
FOLLOW_KW = ["通知", "公告", "学位", "毕业论文", "毕业设计", "研究生", "本科", "学术规范",
             "学术不端", "aigc", "人工智能", "查重", "检测", "诚信", "答辩", "notice", "news", "tzgg"]
SKIP_EXT = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar", ".7z",
            ".jpg", ".jpeg", ".png", ".gif", ".mp4", ".avi")


class SiteAdapter:
    """一所学校的抓取策略。子类按需覆盖 should_follow / seed_urls / extract。"""

    name = "base"

    def match(self, host: str, seed: dict) -> bool:
        return False

    def seed_urls(self, seed: dict) -> list[str]:
        return [seed["entry_url"].strip()]

    def should_follow(self, anchor: str, href: str) -> bool:
        low = (anchor + " " + href).lower()
        if any(href.lower().split("?")[0].endswith(ext) for ext in SKIP_EXT):
            return False
        return any(k in low for k in FOLLOW_KW)

    def page_relevant(self, title: str, body: str) -> bool:
        return extract.page_is_relevant(f"{title}\n{body}")

    def extract(self, title: str, body: str, url: str, seed: dict) -> list[dict]:
        return extract.extract_rules(f"{title}\n{body}", url, seed.get("school_id", ""), seed.get("school_name", ""))


class GenericAdapter(SiteAdapter):
    """默认兜底：对任何学校都适用的关键词驱动策略。"""

    name = "generic"

    def match(self, host: str, seed: dict) -> bool:
        return True
