"""
文本 AIGC 检测器
================

结构（对齐 legacy/algorithms/train_text_detector.py · RobertaAIGCDetector）：
    RoBERTa (chinese-roberta-wwm-ext) → [CLS] embedding (768)
        → Dropout(0.1) → Linear(768, 256) → ReLU → Dropout(0.1) → Linear(256, 2)
        → logits [B, 2]

预测（对齐训练脚本第 693 / 712-713 行）：
    raw_logit    = logits[:, 1]                     # 训练时校准输入即此
    ai_prob      = sigmoid(raw_logit)               # 未校准 AI 概率
    calibrated   = sigmoid((raw_logit / T) * a + b) # 温度缩放 + Platt

checkpoint 期望字段（对齐训练脚本第 754-760 行）：
    - model_state_dict         优先加载（含 roberta 底座）
    - 或 classifier_state_dict + 独立 roberta base_model_path
    - temperature              float
    - platt_a, platt_b         float
    - hyperparams.max_length   int，用于 tokenizer 截断

⚠ 现状：本模块当前只是「加载器 + 校准 + 推理管线」骨架。目录 models/ 里的
aigc_detector_v3_thesis.pth 是 legacy/algorithms/ 老训练脚本产出的实验权重，
不是本次 C 端产品线的正式模型；新一代生产模型的训练计划尚未启动。
将其挂上来的目的是先把「Java → Python 真实推理 → 校准 → 前端展示」链路
打通，替换 MD5 stub；等新模型训完，替换 checkpoint 路径即可，本模块与接口无需改。
"""
from __future__ import annotations

import logging
import math
import os
import re
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer

log = logging.getLogger(__name__)


# ============================================================
# 模型结构（跟 train_text_detector.py 严格对齐）
# ============================================================

class RobertaAIGCDetector(nn.Module):
    def __init__(self, base_model_path: str):
        super().__init__()
        self.roberta = AutoModel.from_pretrained(
            base_model_path, trust_remote_code=True, local_files_only=os.path.isdir(base_model_path)
        )
        hidden = self.roberta.config.hidden_size
        self.classifier = nn.Sequential(
            nn.Dropout(0.1),
            nn.Linear(hidden, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, 2),
        )

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        outputs = self.roberta(input_ids=input_ids, attention_mask=attention_mask)
        cls_emb = outputs.last_hidden_state[:, 0, :]
        return self.classifier(cls_emb)   # [B, 2]


# ============================================================
# 预测结果
# ============================================================

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
    ai_prob: float            # 未校准
    calibrated_prob: float    # 温度 + Platt 校准
    raw_logit: float
    temperature: float
    platt_a: float
    platt_b: float
    model_version: str
    sentences: list[SentencePrediction]


# ============================================================
# 检测器（load once + predict many）
# ============================================================

_SENT_SPLIT = re.compile(r"(?<=[。！？!?.])\s*")


class TextAIGCDetector:
    """
    单例式：由 main.py startup 加载一次；请求线程内 forward eval 无副作用。
    """

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

        # 校准参数（load 之后填充）
        self.temperature: float = 1.0
        self.platt_a: float = 1.0
        self.platt_b: float = 0.0

        self.tokenizer = None
        self.model: RobertaAIGCDetector | None = None

    def load(self) -> None:
        log.info("loading tokenizer from %s", self.base_model_path)
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.base_model_path, trust_remote_code=True,
            local_files_only=os.path.isdir(self.base_model_path),
        )

        log.info("initializing RobertaAIGCDetector")
        model = RobertaAIGCDetector(self.base_model_path).to(self.device)

        log.info("loading checkpoint %s (map to %s)", self.checkpoint_path, self.device)
        ckpt = torch.load(self.checkpoint_path, map_location=self.device, weights_only=False)

        # 优先加载整模型 state；退回只加分类头
        if "model_state_dict" in ckpt:
            missing, unexpected = model.load_state_dict(ckpt["model_state_dict"], strict=False)
            if missing:    log.warning("state_dict missing keys: %d (first=%s)", len(missing), missing[:3])
            if unexpected: log.warning("state_dict unexpected keys: %d (first=%s)", len(unexpected), unexpected[:3])
        elif "classifier_state_dict" in ckpt:
            model.classifier.load_state_dict(ckpt["classifier_state_dict"])
            log.warning("only classifier loaded; roberta uses base pretrained weights")
        else:
            raise ValueError("checkpoint missing both model_state_dict and classifier_state_dict")

        model.eval()
        self.model = model

        # 校准参数
        self.temperature = float(ckpt.get("temperature", 1.0)) or 1.0
        self.platt_a     = float(ckpt.get("platt_a",     1.0))
        self.platt_b     = float(ckpt.get("platt_b",     0.0))

        # 尝试从 hyperparams 覆盖 max_length
        hp = ckpt.get("hyperparams") or {}
        if isinstance(hp, dict) and hp.get("max_length"):
            self.max_length = int(hp["max_length"])

        log.info(
            "text detector ready · T=%.3f a=%.3f b=%.3f max_len=%d device=%s",
            self.temperature, self.platt_a, self.platt_b, self.max_length, self.device,
        )

    # ------------------------------------------------------------------
    # 预测
    # ------------------------------------------------------------------

    @torch.inference_mode()
    def _forward_logit(self, text: str) -> float:
        assert self.tokenizer is not None and self.model is not None, "detector not loaded"
        enc = self.tokenizer(
            text or "",
            truncation=True, max_length=self.max_length,
            padding=False, return_tensors="pt",
        )
        input_ids = enc["input_ids"].to(self.device)
        attn_mask = enc["attention_mask"].to(self.device)
        logits = self.model(input_ids, attn_mask)   # [1, 2]
        # 训练脚本对齐：val_logits_list.extend(logits[:, 1])
        return float(logits[0, 1].item())

    def _calibrate(self, raw_logit: float) -> tuple[float, float]:
        """
        return (ai_prob 未校准, calibrated_prob)
        公式：ai_prob = sigmoid(logit)；calibrated = sigmoid((logit / T) * a + b)
        """
        ai = _sigmoid(raw_logit)
        cal = _sigmoid((raw_logit / max(self.temperature, 1e-3)) * self.platt_a + self.platt_b)
        return ai, cal

    def predict_paragraph(self, text: str, with_sentences: bool = False) -> ParagraphPrediction:
        raw = self._forward_logit(text)
        ai, cal = self._calibrate(raw)

        sentences: list[SentencePrediction] = []
        if with_sentences:
            for idx, (start, end, sent) in enumerate(_split_sentences(text)):
                if not sent.strip():
                    continue
                s_raw = self._forward_logit(sent)
                s_ai, s_cal = self._calibrate(s_raw)
                sentences.append(SentencePrediction(
                    sentence_idx=idx,
                    offset_start=start, offset_end=end,
                    text=sent,
                    ai_prob=round(s_ai, 4),
                    calibrated_prob=round(s_cal, 4),
                ))

        return ParagraphPrediction(
            ai_prob=round(ai, 4),
            calibrated_prob=round(cal, 4),
            raw_logit=round(raw, 4),
            temperature=self.temperature,
            platt_a=self.platt_a,
            platt_b=self.platt_b,
            model_version=self.model_version,
            sentences=sentences,
        )

    def health(self) -> dict[str, Any]:
        return {
            "loaded": self.model is not None,
            "base_model_path": self.base_model_path,
            "checkpoint_path": self.checkpoint_path,
            "device": str(self.device),
            "max_length": self.max_length,
            "temperature": self.temperature,
            "platt_a": self.platt_a,
            "platt_b": self.platt_b,
            "model_version": self.model_version,
        }


# ============================================================
# helpers
# ============================================================

def _sigmoid(x: float) -> float:
    # 稳定版：避免 exp overflow
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _split_sentences(text: str) -> list[tuple[int, int, str]]:
    """
    按中英句末标点切段，返回 [(start, end, sent), ...]
    与 stub 版本口径一致，保持 offset 精确以便前端高亮。
    """
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
