"""
checkpoint 读写契约（训练 / 评估 / 推理三侧共用）
=================================================

best.pth 结构::

    {
      "model_state_dict": {...},
      "temperature": float, "platt_a": float, "platt_b": float,     # 校准（推理公式见 calibration.py）
      "thresholds": {"default_0_5": 0.5, "fpr_1pct": ..., "fpr_5pct": ..., "youden": ...},
      "hyperparams": {
          "version": "v0.2.0-fusion-mdeberta", "codename": "fusion",
          "backbone": "microsoft/mdeberta-v3-base", "arch": "fusion" | "cls_only",
          "max_length": 512, "classifier_hidden": 256, "dropout": 0.1,
          "cnn_kernels": [2,3,5], "cnn_filters": 128, "surface_hidden": 64, "surface_dim": 30,
          "num_sources": 9, "source_families": [...],
          "surface_scaler": {"version": "sf-v1", "names": [...], "mean": [...], "std": [...]}
      },
      "metrics": {...},
      # legacy 兼容键（老推理代码 / VERSIONS.md 登记用）
      "val_acc": float, "val_f1": float, "ece": float
    }

老 checkpoint（legacy/algorithms 产出）没有 hyperparams.arch，按 cls_only + 外部传入的 backbone 路径加载。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import torch
from transformers import AutoTokenizer

from ml.common.fusion_model import ARCH_CLS_ONLY, FusionAIGCDetector
from ml.common.surface_features import SURFACE_DIM, SurfaceScaler


@dataclass
class LoadedDetector:
    model: FusionAIGCDetector
    tokenizer: Any
    scaler: SurfaceScaler
    hparams: dict
    temperature: float
    platt_a: float
    platt_b: float
    thresholds: dict[str, float] = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    is_legacy: bool = False

    @property
    def arch(self) -> str:
        return self.hparams.get("arch", ARCH_CLS_ONLY)

    @property
    def max_length(self) -> int:
        return int(self.hparams.get("max_length", 512))

    @property
    def uses_surface(self) -> bool:
        return self.arch != ARCH_CLS_ONLY


def build_model_from_hparams(hp: dict, local_files_only: bool = False,
                             base_model_override: str | None = None) -> FusionAIGCDetector:
    backbone = base_model_override or hp.get("backbone")
    if not backbone:
        raise ValueError("checkpoint.hyperparams 缺 backbone，且未传 base_model_override")
    return FusionAIGCDetector(
        backbone=backbone,
        arch=hp.get("arch", ARCH_CLS_ONLY),
        num_classes=int(hp.get("num_classes", 2)),
        classifier_hidden=int(hp.get("classifier_hidden", 256)),
        dropout=float(hp.get("dropout", 0.1)),
        cnn_kernels=tuple(hp.get("cnn_kernels", (2, 3, 5))),
        cnn_filters=int(hp.get("cnn_filters", 128)),
        surface_dim=int(hp.get("surface_dim", SURFACE_DIM)),
        surface_hidden=int(hp.get("surface_hidden", 64)),
        num_sources=int(hp.get("num_sources", 0)),
        gradient_checkpointing=False,
        local_files_only=local_files_only or os.path.isdir(str(backbone)),
    )


def _remap_legacy_keys(state: dict) -> dict:
    """legacy 权重前缀是 roberta.*，新模型是 backbone.*。"""
    if any(k.startswith("roberta.") for k in state):
        return {("backbone." + k[len("roberta."):] if k.startswith("roberta.") else k): v for k, v in state.items()}
    return state


def load_detector_from_checkpoint(
    checkpoint_path: str,
    device: str | torch.device = "cpu",
    base_model_override: str | None = None,
    strict: bool = False,
) -> LoadedDetector:
    device = torch.device(device)
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    hp = dict(ckpt.get("hyperparams") or {})
    is_legacy = "arch" not in hp
    if is_legacy:
        hp.setdefault("arch", ARCH_CLS_ONLY)
        hp.setdefault("backbone", base_model_override)
        hp.setdefault("max_length", hp.get("max_length", 512))

    model = build_model_from_hparams(hp, base_model_override=base_model_override).to(device)
    state = ckpt.get("model_state_dict")
    if state is None:
        raise ValueError("checkpoint 缺 model_state_dict")
    state = _remap_legacy_keys(state)
    missing, unexpected = model.load_state_dict(state, strict=strict)
    if missing or unexpected:
        import logging
        logging.getLogger(__name__).warning(
            "load_state_dict: missing=%d unexpected=%d (first missing=%s)", len(missing), len(unexpected), missing[:3]
        )
    model.eval()

    tok_path = base_model_override or hp.get("backbone")
    tokenizer = AutoTokenizer.from_pretrained(tok_path, trust_remote_code=True, local_files_only=os.path.isdir(str(tok_path)))
    scaler = SurfaceScaler.from_dict(hp.get("surface_scaler"))

    return LoadedDetector(
        model=model,
        tokenizer=tokenizer,
        scaler=scaler,
        hparams=hp,
        temperature=float(ckpt.get("temperature", 1.0)) or 1.0,
        platt_a=float(ckpt.get("platt_a", 1.0)),
        platt_b=float(ckpt.get("platt_b", 0.0)),
        thresholds=dict(ckpt.get("thresholds") or {"default_0_5": 0.5}),
        metrics=dict(ckpt.get("metrics") or {}),
        is_legacy=is_legacy,
    )


def save_checkpoint(
    path: str,
    model: FusionAIGCDetector,
    hparams: dict,
    temperature: float,
    platt_a: float,
    platt_b: float,
    thresholds: dict[str, float],
    metrics: dict,
) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload = {
        "model_state_dict": {k: v.detach().cpu() for k, v in model.state_dict().items()},
        "temperature": float(temperature),
        "platt_a": float(platt_a),
        "platt_b": float(platt_b),
        "thresholds": {k: float(v) for k, v in thresholds.items()},
        "hyperparams": hparams,
        "metrics": metrics,
        # legacy 兼容键
        "val_acc": float(metrics.get("val", {}).get("accuracy", 0.0)),
        "val_f1": float(metrics.get("val", {}).get("f1", 0.0)),
        "ece": float(metrics.get("val", {}).get("ece_after", 0.0)),
    }
    torch.save(payload, path)
