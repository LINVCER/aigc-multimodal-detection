"""
文本 AIGC 检测器（推理侧）
==========================

模型定义与 checkpoint 契约统一走 ml/common（fusion_model / checkpoint / surface_features），
本文件只负责：加载 → 段落 / 句子推理 → 校准 → 结果结构。

支持两代 checkpoint：
    - 新：ml/training/text/train.py 产出，hyperparams.arch ∈ {fusion, cls_only}，自带 backbone / 表层特征 scaler / 阈值
    - 老：legacy/algorithms 产出（无 arch），按 cls_only + TEXT_BASE_MODEL_PATH 加载（向后兼容）

预测公式（与训练侧 calibration.py 一致）：
    raw_logit  = logits[:, 1]
    ai_prob    = sigmoid(raw_logit)
    calibrated = sigmoid((raw_logit / T) * a + b)

import 说明：ml/ 与 deploy/inference-python 在同一仓库；容器内由 Dockerfile 把 ml/common 拷到 /app/ml/common，
本地直跑时把仓库根加进 sys.path。
"""
from __future__ import annotations

import logging
import math
import os
import sys
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import torch

_HERE = os.path.dirname(os.path.abspath(__file__))
for cand in (os.path.dirname(_HERE), os.path.abspath(os.path.join(_HERE, "..", "..", ".."))):
    if os.path.isdir(os.path.join(cand, "ml", "common")) and cand not in sys.path:
        sys.path.insert(0, cand)

from ml.common.checkpoint import LoadedDetector, load_detector_from_checkpoint  # noqa: E402
from ml.common.surface_features import extract_surface_features  # noqa: E402

log = logging.getLogger(__name__)


@dataclass
class SentencePrediction:
    sentence_idx: int
    offset_start: int
    offset_end: int
    text: str
    ai_prob: float
    calibrated_prob: float


@dataclass
class ParagraphPrediction:
    ai_prob: float
    calibrated_prob: float
    raw_logit: float
    temperature: float
    platt_a: float
    platt_b: float
    model_version: str
    sentences: list[SentencePrediction]
    thresholds: dict[str, float] = field(default_factory=dict)
    source_probs: dict[str, float] = field(default_factory=dict)   # 溯源头（fusion 且 use_source_head 时有）


class TextAIGCDetector:
    """单例式：main.py startup 加载一次；请求线程内 forward eval 无副作用。"""

    def __init__(
        self,
        base_model_path: str,
        checkpoint_path: str,
        device: str = "cpu",
        max_length: int = 512,
        model_version: str = "aigc_v3_thesis",
    ) -> None:
        self.base_model_path = base_model_path
        self.checkpoint_path = checkpoint_path
        self.device = torch.device(device)
        self.max_length = max_length
        self.model_version = model_version
        self.temperature, self.platt_a, self.platt_b = 1.0, 1.0, 0.0
        self.thresholds: dict[str, float] = {"default_0_5": 0.5}
        self._det: LoadedDetector | None = None

    # ------------------------------------------------------------------
    def load(self) -> None:
        log.info("loading checkpoint %s (device=%s)", self.checkpoint_path, self.device)
        det = load_detector_from_checkpoint(
            self.checkpoint_path, device=self.device,
            base_model_override=self.base_model_path or None,
        )
        self._det = det
        self.temperature, self.platt_a, self.platt_b = det.temperature, det.platt_a, det.platt_b
        self.thresholds = det.thresholds
        self.max_length = det.max_length or self.max_length
        if det.hparams.get("version"):
            self.model_version = str(det.hparams["version"])
        log.info(
            "text detector ready · arch=%s legacy=%s backbone=%s T=%.3f a=%.3f b=%.3f max_len=%d thresholds=%s",
            det.arch, det.is_legacy, det.hparams.get("backbone"), self.temperature, self.platt_a, self.platt_b,
            self.max_length, {k: round(v, 3) for k, v in self.thresholds.items()},
        )

    # ------------------------------------------------------------------
    @torch.inference_mode()
    def _forward(self, text: str) -> tuple[float, dict[str, float]]:
        assert self._det is not None, "detector not loaded"
        det = self._det
        enc = det.tokenizer(text or "", truncation=True, max_length=self.max_length, padding=False, return_tensors="pt")
        ids = enc["input_ids"].to(self.device)
        mask = enc["attention_mask"].to(self.device)
        surf = None
        if det.uses_surface:
            feats = det.scaler.transform(extract_surface_features(text)[None])
            surf = torch.as_tensor(feats, dtype=torch.float32, device=self.device)
        out = det.model(ids, mask, surface=surf, return_source=True)
        logits, src_logits, _ = out if isinstance(out, tuple) else (out, None, None)
        source_probs: dict[str, float] = {}
        if src_logits is not None and det.hparams.get("source_families"):
            probs = torch.softmax(src_logits[0].float(), dim=-1).cpu().numpy()
            source_probs = {n: round(float(p), 4) for n, p in zip(det.hparams["source_families"], probs)}
        return float(logits[0, 1].item()), source_probs

    def _calibrate(self, raw_logit: float) -> tuple[float, float]:
        ai = _sigmoid(raw_logit)
        cal = _sigmoid((raw_logit / max(self.temperature, 1e-3)) * self.platt_a + self.platt_b)
        return ai, cal

    def predict_paragraph(self, text: str, with_sentences: bool = False) -> ParagraphPrediction:
        raw, source_probs = self._forward(text)
        ai, cal = self._calibrate(raw)
        sentences: list[SentencePrediction] = []
        if with_sentences:
            for idx, (start, end, sent) in enumerate(_split_sentences(text)):
                if not sent.strip():
                    continue
                s_raw, _ = self._forward(sent)
                s_ai, s_cal = self._calibrate(s_raw)
                sentences.append(SentencePrediction(idx, start, end, sent, round(s_ai, 4), round(s_cal, 4)))
        return ParagraphPrediction(
            ai_prob=round(ai, 4), calibrated_prob=round(cal, 4), raw_logit=round(raw, 4),
            temperature=self.temperature, platt_a=self.platt_a, platt_b=self.platt_b,
            model_version=self.model_version, sentences=sentences,
            thresholds=self.thresholds, source_probs=source_probs,
        )

    def health(self) -> dict[str, Any]:
        det = self._det
        return {
            "loaded": det is not None,
            "arch": det.arch if det else None,
            "legacy_checkpoint": det.is_legacy if det else None,
            "backbone": (det.hparams.get("backbone") if det else self.base_model_path),
            "checkpoint_path": self.checkpoint_path,
            "device": str(self.device),
            "max_length": self.max_length,
            "temperature": self.temperature, "platt_a": self.platt_a, "platt_b": self.platt_b,
            "thresholds": self.thresholds,
            "model_version": self.model_version,
            "val_metrics": (det.metrics.get("val", {}) if det else {}),
        }


# ---------------------------------------------------------------------------
def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


def _split_sentences(text: str) -> list[tuple[int, int, str]]:
    """按中英句末标点切段，返回 [(start, end, sent)]，offset 精确以便前端高亮。"""
    out: list[tuple[int, int, str]] = []
    if not text:
        return out
    start, cursor = 0, 0
    for ch in text:
        cursor += 1
        if ch in "。！？!?." and cursor - start > 5:
            out.append((start, cursor, text[start:cursor]))
            start = cursor
    if start < len(text):
        out.append((start, len(text), text[start:]))
    return out
