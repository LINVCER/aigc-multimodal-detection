"""
适配器注册表
============

把具体学校适配器实例加进 _REGISTRY（顺序在前者优先），都不命中时用 GenericAdapter 兜底。
新增一所特殊学校：在同目录建 <school>.py 写子类，在这里 import 并 append。
"""
from __future__ import annotations

from urllib.parse import urlparse

from adapters.base import GenericAdapter, SiteAdapter

# 具体学校适配器（页面结构特殊、列表要翻页、正文在某个固定容器里时才需要）
_REGISTRY: list[SiteAdapter] = [
    # 一校一适配器：确认网站 → 复制 adapters/example_school.py 改名 → 在此 import 并 append
    # 例：from adapters.nwpu import NwpuAdapter; NwpuAdapter(),
]
_GENERIC = GenericAdapter()


def get_adapter(seed: dict) -> SiteAdapter:
    host = urlparse(seed.get("entry_url", "")).netloc
    for a in _REGISTRY:
        if a.match(host, seed):
            return a
    return _GENERIC
