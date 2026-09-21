"""
特征融合检测器（训练 / 推理共用的模型定义）
==========================================

结构（Chen 2026 · RoBERTa-CNN 特征级融合，见文献精读笔记 §五）::

    backbone(input_ids, mask) → last_hidden_state [B, L, H]
        ├─ h_cls = hidden[:, 0]                                  [B, H]
        ├─ h_cnn = concat_k( maxpool( ReLU( Conv1d_k(hidden) ) ) )  [B, F * |K|]
        └─ f     = MLP( z-scored surface features )               [B, S]
    fused = LayerNorm( [h_cls ; h_cnn ; f] )
    logits        = classifier(fused)      [B, 2]      主任务 human / ai
    source_logits = source_head(fused)     [B, n_src]  可选溯源头（共享表示，multi-task）

arch = "cls_only" 时退化为 legacy 结构（[CLS] → MLP），用于 A/B 对照与向后兼容老 checkpoint。

放在 ml/common 而非 ml/training 的原因：deploy/inference-python 也要 import 同一份定义，
避免推理侧手抄一份后与训练侧漂移（老代码 detectors/text.py 就是这么出问题的）。
"""
from __future__ import annotations

from typing import Sequence

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModel

ARCH_CLS_ONLY = "cls_only"
ARCH_FUSION = "fusion"
ARCHS = (ARCH_CLS_ONLY, ARCH_FUSION)


class MultiScaleTextCNN(nn.Module):
    """对 token 级 hidden states 做多尺度一维卷积 + 全局最大池化，抓局部 n-gram 级结构模式。"""

    def __init__(self, in_dim: int, kernels: Sequence[int] = (2, 3, 5), filters: int = 128, dropout: float = 0.1):
        super().__init__()
        self.convs = nn.ModuleList([
            nn.Conv1d(in_dim, filters, kernel_size=k, padding=k // 2) for k in kernels
        ])
        self.dropout = nn.Dropout(dropout)
        self.out_dim = filters * len(kernels)

    def forward(self, hidden: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        # hidden [B, L, H] → [B, H, L]；padding 位置置 -inf 再 max-pool，避免 pad 干扰
        x = hidden.transpose(1, 2)
        mask = attention_mask.unsqueeze(1).to(dtype=torch.bool)   # [B, 1, L]
        outs = []
        for conv in self.convs:
            c = F.relu(conv(x))                                    # [B, F, L']（padding=k//2 时 L' 可能 = L 或 L+1）
            c = c[..., : mask.shape[-1]]
            c = c.masked_fill(~mask, float("-inf"))
            outs.append(c.max(dim=-1).values)                      # [B, F]
        return self.dropout(torch.cat(outs, dim=-1))


class FusionAIGCDetector(nn.Module):
    def __init__(
        self,
        backbone: str,
        arch: str = ARCH_FUSION,
        num_classes: int = 2,
        classifier_hidden: int = 256,
        dropout: float = 0.1,
        cnn_kernels: Sequence[int] = (2, 3, 5),
        cnn_filters: int = 128,
        surface_dim: int = 30,
        surface_hidden: int = 64,
        num_sources: int = 0,
        gradient_checkpointing: bool = False,
        local_files_only: bool = False,
    ) -> None:
        super().__init__()
        if arch not in ARCHS:
            raise ValueError(f"arch 必须是 {ARCHS}，得到 {arch!r}")
        self.arch = arch
        self.num_sources = num_sources
        self.surface_dim = surface_dim

        self.backbone = AutoModel.from_pretrained(
            backbone, trust_remote_code=True, local_files_only=local_files_only
        )
        if gradient_checkpointing and hasattr(self.backbone, "gradient_checkpointing_enable"):
            self.backbone.gradient_checkpointing_enable()
        hidden = self.backbone.config.hidden_size

        if arch == ARCH_FUSION:
            self.cnn = MultiScaleTextCNN(hidden, cnn_kernels, cnn_filters, dropout)
            self.surface_mlp = nn.Sequential(
                nn.Linear(surface_dim, surface_hidden),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(surface_hidden, surface_hidden),
                nn.GELU(),
            )
            fused_dim = hidden + self.cnn.out_dim + surface_hidden
            self.fuse_norm = nn.LayerNorm(fused_dim)
        else:
            self.cnn = None
            self.surface_mlp = None
            fused_dim = hidden
            self.fuse_norm = nn.Identity()
        self.fused_dim = fused_dim

        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(fused_dim, classifier_hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(classifier_hidden, num_classes),
        )
        self.source_head = (
            nn.Sequential(nn.Dropout(dropout), nn.Linear(fused_dim, 128), nn.ReLU(), nn.Linear(128, num_sources))
            if num_sources > 0 else None
        )

    # ------------------------------------------------------------------
    def encode(self, input_ids: torch.Tensor, attention_mask: torch.Tensor,
               surface: torch.Tensor | None = None) -> torch.Tensor:
        out = self.backbone(input_ids=input_ids, attention_mask=attention_mask)
        hidden = out.last_hidden_state
        h_cls = hidden[:, 0, :]
        if self.arch == ARCH_CLS_ONLY:
            return h_cls
        if surface is None:
            surface = torch.zeros(input_ids.shape[0], self.surface_dim, device=input_ids.device, dtype=h_cls.dtype)
        h_cnn = self.cnn(hidden, attention_mask)
        f = self.surface_mlp(surface.to(dtype=h_cls.dtype))
        return self.fuse_norm(torch.cat([h_cls, h_cnn, f], dim=-1))

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        surface: torch.Tensor | None = None,
        return_source: bool = False,
        return_emb: bool = False,
    ):
        fused = self.encode(input_ids, attention_mask, surface)
        logits = self.classifier(fused)
        if not (return_source or return_emb):
            return logits
        source_logits = self.source_head(fused) if (return_source and self.source_head is not None) else None
        return logits, source_logits, (fused if return_emb else None)

    # ------------------------------------------------------------------
    def encoder_layers(self) -> list[nn.Module]:
        """兼容 BERT/RoBERTa（.encoder.layer）与 DeBERTa-v2/v3（.encoder.layer）；其它结构返回空列表。"""
        enc = getattr(self.backbone, "encoder", None)
        layers = getattr(enc, "layer", None)
        return list(layers) if layers is not None else []


def freeze_backbone_except_last(model: FusionAIGCDetector, unfreeze_layers: int) -> tuple[int, int]:
    """
    冻结 embeddings 与底部若干 encoder 层，只训最后 unfreeze_layers 层 + 全部融合 / 分类头。
    unfreeze_layers <= 0 表示整个 backbone 全冻结（线性探测）；>= 总层数表示全解冻。
    返回 (冻结层数, 总层数)。
    """
    layers = model.encoder_layers()
    total = len(layers)
    for p in model.backbone.parameters():
        p.requires_grad = False
    n_unfreeze = max(0, min(unfreeze_layers, total))
    for layer in layers[total - n_unfreeze:]:
        for p in layer.parameters():
            p.requires_grad = True
    # DeBERTa 的相对位置 embedding 在 encoder 里（rel_embeddings / LayerNorm），随最后几层一起解冻
    enc = getattr(model.backbone, "encoder", None)
    for name in ("rel_embeddings", "LayerNorm", "conv"):
        mod = getattr(enc, name, None)
        if mod is not None and n_unfreeze > 0:
            for p in mod.parameters():
                p.requires_grad = True
    return total - n_unfreeze, total
