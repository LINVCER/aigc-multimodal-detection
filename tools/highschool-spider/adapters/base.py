"""
站点适配器基类 + 通用适配器
============================

借 spider-v2 的 platforms/<name>/ 思路：每所页面结构特殊的学校可写一个子类覆盖，
大多数学校走 GenericAdapter（关键词驱动）即可。调度器按注册表选第一个 match 的，兜底用 generic。
"""
from __future__ import annotations

import re

import extract

# 链接是否值得跟进：锚文本或 URL 命中这些词才入队，避免把整站爬一遍
FOLLOW_KW = ["通知", "公告", "学位", "毕业论文", "毕业设计", "研究生", "本科", "学术规范",
             "学术不端", "aigc", "人工智能", "查重", "检测", "诚信", "答辩", "notice", "news", "tzgg",
             "yjsy", "gs", "grad", "jwc", "教务", "学位办", "质量"]
# 深度模式额外跟进：研究生院/教务处/学位办等子站入口，哪怕锚文本没命中关键词
DEEP_SITE_KW = ["yjsy", "gs.", "grad", "jwc", "xwb", "yb.", "/gra", "/yjs", "/jw"]
IMG_MEDIA_EXT = (".xls", ".xlsx", ".zip", ".rar", ".7z", ".jpg", ".jpeg", ".png", ".gif", ".mp4", ".avi", ".mp3")
ATTACH_EXT = (".pdf", ".doc", ".docx")
# 列表翻页：index_2.html / list2.htm / ?page=2 / _2.html 等
_PAGER = re.compile(r"(?:index|list)?_?\d{1,3}\.(?:html?|shtml)$|[?&](?:page|pageNum|pn)=\d+")


class SiteAdapter:
    """一所学校的抓取策略。子类按需覆盖 should_follow / seed_urls / extract。"""

    name = "base"
    deep = False  # 由 spider 按 --deep 设置：放宽跟进、跟进翻页与子站

    def match(self, host: str, seed: dict) -> bool:
        return False

    def seed_urls(self, seed: dict) -> list[str]:
        return [seed["entry_url"].strip()]

    def is_attachment(self, href: str) -> bool:
        return href.lower().split("?")[0].endswith(ATTACH_EXT)

    def should_follow(self, anchor: str, href: str) -> bool:
        path = href.lower().split("?")[0]
        if path.endswith(IMG_MEDIA_EXT):
            return False
        if path.endswith(ATTACH_EXT):
            return False  # 附件单独走 is_attachment，不走 html 跟进
        low = (anchor + " " + href).lower()
        if any(k in low for k in FOLLOW_KW):
            return True
        if self.deep:
            # 深度模式：翻页与研究生院/教务处子站入口也跟，公开页没有时尽量往深走
            if _PAGER.search(href):
                return True
            if any(k in low for k in DEEP_SITE_KW):
                return True
        return False

    def page_relevant(self, title: str, body: str) -> bool:
        return extract.page_is_relevant(f"{title}\n{body}")

    def extract(self, title: str, body: str, url: str, seed: dict) -> list[dict]:
        return extract.extract_rules(f"{title}\n{body}", url, seed.get("school_id", ""), seed.get("school_name", ""))


class GenericAdapter(SiteAdapter):
    """默认兜底：对任何学校都适用的关键词驱动策略。"""

    name = "generic"

    def match(self, host: str, seed: dict) -> bool:
        return True
