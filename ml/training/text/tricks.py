"""训练技巧：EMA / FGM 对抗扰动 / 分层学习率 / 随机种子。沿用 legacy 脚本验证过的做法，接口精简。"""
from __future__ import annotations

import os
import random

import numpy as np
import torch
import torch.nn as nn


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


class EMA:
    """参数指数移动平均；验证与保存用 shadow 权重，训练继续用原权重。"""

    def __init__(self, model: nn.Module, decay: float = 0.999) -> None:
        self.model = model
        self.decay = decay
        self.shadow: dict[str, torch.Tensor] = {
            n: p.detach().clone() for n, p in model.named_parameters() if p.requires_grad
        }
        self.backup: dict[str, torch.Tensor] = {}

    @torch.no_grad()
    def update(self) -> None:
        for n, p in self.model.named_parameters():
            if p.requires_grad and n in self.shadow:
                self.shadow[n].mul_(self.decay).add_(p.detach(), alpha=1.0 - self.decay)

    def apply_shadow(self) -> None:
        for n, p in self.model.named_parameters():
            if n in self.shadow:
                self.backup[n] = p.data.clone()
                p.data.copy_(self.shadow[n])

    def restore(self) -> None:
        for n, p in self.model.named_parameters():
            if n in self.backup:
                p.data.copy_(self.backup[n])
        self.backup.clear()


class FGM:
    """Fast Gradient Method：沿 embedding 梯度方向加 ε 扰动再算一次 loss，提升对字面级扰动的鲁棒性。"""

    def __init__(self, model: nn.Module, epsilon: float = 0.5, target: str = "embeddings.word_embeddings") -> None:
        self.model = model
        self.epsilon = epsilon
        self.target = target
        self.backup: dict[str, torch.Tensor] = {}

    def attack(self) -> None:
        for n, p in self.model.named_parameters():
            if p.requires_grad and self.target in n and p.grad is not None:
                self.backup[n] = p.data.clone()
                norm = torch.norm(p.grad)
                if norm > 0 and not torch.isnan(norm):
                    p.data.add_(self.epsilon * p.grad / norm)

    def restore(self) -> None:
        for n, p in self.model.named_parameters():
            if n in self.backup:
                p.data.copy_(self.backup[n])
        self.backup.clear()


def build_param_groups(
    model: nn.Module,
    lr: float,
    weight_decay: float = 0.01,
    bottom_factor: float = 0.1,
    mid_factor: float = 0.5,
    head_factor: float = 5.0,
    n_layers: int | None = None,
) -> list[dict]:
    """
    分层学习率：backbone 底层小步、顶层正常、融合 / 分类头大步。
    LayerNorm 与 bias 不做 weight decay（HF 惯例）。
    """
    layers = getattr(getattr(model, "backbone", None), "encoder", None)
    layers = getattr(layers, "layer", None)
    n_layers = n_layers or (len(layers) if layers is not None else 12)

    def bucket(name: str) -> str:
        if "backbone" not in name:
            return "head"
        if ".encoder.layer." in name:
            idx = int(name.split(".encoder.layer.")[1].split(".")[0])
            if idx < n_layers // 2:
                return "bottom"
            if idx < n_layers - 2:
                return "mid"
            return "top"
        return "bottom"   # embeddings / rel_embeddings 等

    factors = {"bottom": bottom_factor, "mid": mid_factor, "top": 1.0, "head": head_factor}
    groups: dict[tuple[str, bool], list[torch.Tensor]] = {}
    for n, p in model.named_parameters():
        if not p.requires_grad:
            continue
        no_decay = n.endswith(".bias") or "LayerNorm" in n or "layer_norm" in n or "norm" in n.lower()
        groups.setdefault((bucket(n), no_decay), []).append(p)

    out = []
    for (b, nd), params in groups.items():
        out.append({"params": params, "lr": lr * factors[b], "weight_decay": 0.0 if nd else weight_decay, "name": f"{b}{'_nodecay' if nd else ''}"})
    return out
