"""
v0.1.0-baseline 数据加载
=======================

JSONL 格式约定（每行）:
    {"text": "...", "label": 0|1, "scenario": "academic_master", "source": "human|gpt|..."}

- label:    0 = 人类, 1 = AI
- scenario: 6 场景之一（academic_bachelor / academic_master / academic_phd
            / job_report / self_media / other）
- source:   细粒度来源（供未来溯源多任务用；v0.1.0 不训 source 头）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class TextSample:
    text: str
    label: int
    scenario: str
    source: str = "unknown"


# TODO(v0.1.0)
def load_jsonl(path: str) -> list[TextSample]:
    raise NotImplementedError("待 v0.1.0 数据准备完成后实现")


# TODO(v0.1.0)：分场景等比采样，避免"academic_master 淹没其它场景"偏科
def scenario_balanced_sampler(samples: Iterable[TextSample], mix: dict[str, float]) -> list[TextSample]:
    raise NotImplementedError("待 v0.1.0 训练启动时实现")
