"""
训练数据加载 / 采样 / Dataset
============================

JSONL schema 见 ml/datasets/text/schema.py。本模块负责：
1. load_jsonl：读入 + 长度门槛过滤
2. scenario_balanced_sampler：按 6 场景等比采样，防 academic_master 一家淹没其它场景
3. augment_mix_sampler：控制改写 / 润色 / 混写样本占比（Fraser：mixcase 不入训 → 全线失效）
4. TextAIGCDataset：tokenize + 表层特征 + 轻量在线增强（同义替换 / 句序打乱 / 随机删字）
5. build_collate：动态 padding，省显存
"""
from __future__ import annotations

import random
from collections import defaultdict
from typing import Callable, Iterable, Sequence

import numpy as np
import torch
from torch.utils.data import Dataset

from ml.common.surface_features import SURFACE_DIM, SurfaceScaler, extract_surface_features
from ml.datasets.text.schema import (
    MIN_CHARS,
    SCENARIOS,
    SOURCE_TO_ID,
    TextSample,
    iter_jsonl,
)

__all__ = [
    "TextSample", "load_jsonl", "scenario_balanced_sampler", "augment_mix_sampler",
    "TextAIGCDataset", "build_collate", "fit_surface_scaler",
]


# ---------------------------------------------------------------------------
# 读入 / 采样
# ---------------------------------------------------------------------------

def load_jsonl(path: str, min_chars: int = MIN_CHARS, max_samples: int | None = None) -> list[TextSample]:
    out: list[TextSample] = []
    for s in iter_jsonl(path):
        if len(s.text) < min_chars:
            continue
        out.append(s)
        if max_samples and len(out) >= max_samples:
            break
    return out


def _take(pool: list[TextSample], n: int, rng: random.Random) -> list[TextSample]:
    if n >= len(pool):
        return list(pool)
    return rng.sample(pool, n)


def scenario_balanced_sampler(
    samples: Iterable[TextSample],
    mix: dict[str, float],
    total: int | None = None,
    seed: int = 42,
) -> list[TextSample]:
    """
    按 mix 里的场景比例采样。某场景样本不足时取全量并把缺口按比例分给其它场景，
    保证最终规模 ≈ total（未给 total 时 = 输入规模）。每个场景内部再做 label 均衡。
    """
    rng = random.Random(seed)
    by_sc: dict[str, list[TextSample]] = defaultdict(list)
    for s in samples:
        by_sc[s.scenario].append(s)
    total = total or sum(len(v) for v in by_sc.values())
    weights = {sc: float(mix.get(sc, 0.0)) for sc in SCENARIOS}
    wsum = sum(weights.values()) or 1.0
    weights = {k: v / wsum for k, v in weights.items()}

    out: list[TextSample] = []
    remaining = total
    todo = sorted(weights, key=lambda k: len(by_sc.get(k, [])))   # 从最稀缺场景起分配
    left_weight = 1.0
    for sc in todo:
        want = int(round(remaining * (weights[sc] / left_weight))) if left_weight > 0 else 0
        pool = by_sc.get(sc, [])
        pos = [x for x in pool if x.label == 1]
        neg = [x for x in pool if x.label == 0]
        half = want // 2
        picked = _take(pos, half, rng) + _take(neg, want - half, rng)
        if len(picked) < want:   # 一侧不足则另一侧补
            short = want - len(picked)
            spare = [x for x in pool if x not in picked]
            picked += _take(spare, short, rng)
        out.extend(picked)
        remaining -= len(picked)
        left_weight -= weights[sc]
    rng.shuffle(out)
    return out


def augment_mix_sampler(
    samples: Sequence[TextSample],
    augment_mix: dict[str, float],
    seed: int = 42,
) -> list[TextSample]:
    """
    控制各 augment 类型占比（相对 none 样本）。例如 {"paraphrase_strong": 0.1, "polished": 0.1}
    表示改写 / 润色样本各占最终集合的 ~10%。缺口只削不补（不复制样本）。
    """
    rng = random.Random(seed)
    by_aug: dict[str, list[TextSample]] = defaultdict(list)
    for s in samples:
        by_aug[s.augment].append(s)
    base = by_aug.get("none", [])
    out = list(base)
    base_share = max(1.0 - sum(float(v) for v in augment_mix.values()), 0.05)
    target_total = int(len(base) / base_share)
    for aug, share in augment_mix.items():
        want = int(target_total * float(share))
        out.extend(_take(by_aug.get(aug, []), want, rng))
    # 未在 mix 中提及的 augment 类型全部保留
    for aug, pool in by_aug.items():
        if aug != "none" and aug not in augment_mix:
            out.extend(pool)
    rng.shuffle(out)
    return out


# ---------------------------------------------------------------------------
# 在线轻量增强（无 LLM；LLM 改写在离线 paraphrase_augment.py）
# ---------------------------------------------------------------------------

_SYNONYMS = {
    "非常": "十分", "十分": "非常", "重要": "关键", "关键": "重要", "显著": "明显", "明显": "显著",
    "应用": "运用", "运用": "应用", "发展": "进步", "问题": "议题", "需要": "需求", "可以": "能够",
    "能够": "可以", "进行": "展开", "通过": "借助", "分析": "剖析", "方法": "方式", "方式": "方法",
    "提升": "提高", "提高": "提升", "研究": "探讨", "实现": "达成", "影响": "作用", "作用": "影响",
}
_SENT_END = "。！？!?"


def online_augment(text: str, rng: random.Random, p_synonym: float = 0.15, p_shuffle: float = 0.1,
                   p_delete: float = 0.1) -> str:
    choice = rng.random()
    if choice < p_synonym:
        out = text
        for a, b in _SYNONYMS.items():
            if a in out and rng.random() < 0.3:
                out = out.replace(a, b, 1)
        return out
    if choice < p_synonym + p_shuffle:
        parts, buf = [], []
        for ch in text:
            buf.append(ch)
            if ch in _SENT_END:
                parts.append("".join(buf)); buf = []
        if buf:
            parts.append("".join(buf))
        if len(parts) >= 3:
            i, j = rng.sample(range(len(parts)), 2)
            parts[i], parts[j] = parts[j], parts[i]
        return "".join(parts)
    if choice < p_synonym + p_shuffle + p_delete:
        kept = [c for c in text if rng.random() > 0.05]
        return "".join(kept) if len(kept) >= MIN_CHARS else text
    return text


# ---------------------------------------------------------------------------
# Dataset / collate
# ---------------------------------------------------------------------------

def fit_surface_scaler(samples: Sequence[TextSample], max_samples: int = 20000, seed: int = 42) -> SurfaceScaler:
    rng = random.Random(seed)
    pool = list(samples) if len(samples) <= max_samples else rng.sample(list(samples), max_samples)
    feats = np.stack([extract_surface_features(s.text) for s in pool], axis=0)
    return SurfaceScaler().fit(feats)


class TextAIGCDataset(Dataset):
    def __init__(
        self,
        samples: Sequence[TextSample],
        tokenizer,
        max_length: int = 512,
        scaler: SurfaceScaler | None = None,
        use_surface: bool = True,
        augment_prob: float = 0.0,
        augment_kw: dict | None = None,
        seed: int = 42,
        precompute_surface: bool = True,
    ) -> None:
        self.samples = list(samples)
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.scaler = scaler or SurfaceScaler()
        self.use_surface = use_surface
        self.augment_prob = augment_prob
        self.augment_kw = augment_kw or {}
        self.rng = random.Random(seed)
        # 表层特征在原文上预计算；在线增强后的文本不重算（增强只改语义支路，f 保持原文统计——刻意如此，
        # 让模型学到"表层规律稳定、语义扰动"这一改写场景的真实分布）
        self._surface: np.ndarray | None = None
        if use_surface and precompute_surface:
            raw = np.stack([extract_surface_features(s.text) for s in self.samples], axis=0) if self.samples else np.zeros((0, SURFACE_DIM), np.float32)
            self._surface = self.scaler.transform(raw)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict:
        s = self.samples[idx]
        text = s.text
        if self.augment_prob > 0 and self.rng.random() < self.augment_prob:
            text = online_augment(text, self.rng, **self.augment_kw)
        enc = self.tokenizer(text, max_length=self.max_length, truncation=True, padding=False, return_tensors=None)
        if self.use_surface:
            surf = self._surface[idx] if self._surface is not None else self.scaler.transform(extract_surface_features(text)[None])[0]
        else:
            surf = np.zeros(SURFACE_DIM, np.float32)
        return {
            "input_ids": enc["input_ids"],
            "attention_mask": enc["attention_mask"],
            "label": int(s.label),
            "source_id": SOURCE_TO_ID.get(s.source, SOURCE_TO_ID["other"]),
            "surface": surf,
            "scenario": s.scenario,
            "augment": s.augment,
        }


def build_collate(pad_token_id: int) -> Callable[[list[dict]], dict]:
    def collate(batch: list[dict]) -> dict:
        max_len = max(len(b["input_ids"]) for b in batch)
        ids = torch.full((len(batch), max_len), pad_token_id, dtype=torch.long)
        mask = torch.zeros((len(batch), max_len), dtype=torch.long)
        for i, b in enumerate(batch):
            n = len(b["input_ids"])
            ids[i, :n] = torch.as_tensor(b["input_ids"], dtype=torch.long)
            mask[i, :n] = 1
        return {
            "input_ids": ids,
            "attention_mask": mask,
            "label": torch.as_tensor([b["label"] for b in batch], dtype=torch.long),
            "source_id": torch.as_tensor([b["source_id"] for b in batch], dtype=torch.long),
            "surface": torch.as_tensor(np.stack([b["surface"] for b in batch]), dtype=torch.float32),
            "scenario": [b["scenario"] for b in batch],
            "augment": [b["augment"] for b in batch],
        }
    return collate
