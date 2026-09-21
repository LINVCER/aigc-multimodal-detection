"""训练损失：Focal / Label Smoothing / R-Drop 一致性 / SupCon 对比。"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class FocalLoss(nn.Module):
    """Focal Loss（Lin 2017）：(1-p_t)^γ 压低易样本梯度，把学习压力放到改写 / 润色这类难样本上。"""

    def __init__(self, gamma: float = 2.0, alpha: float = 0.25) -> None:
        super().__init__()
        self.gamma = gamma
        self.alpha = alpha

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce = F.cross_entropy(logits, targets, reduction="none")
        pt = torch.exp(-ce)
        return (self.alpha * (1.0 - pt) ** self.gamma * ce).mean()


class LabelSmoothingLoss(nn.Module):
    def __init__(self, epsilon: float = 0.1, num_classes: int = 2) -> None:
        super().__init__()
        self.epsilon = epsilon
        self.num_classes = num_classes

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        log_probs = F.log_softmax(logits, dim=-1)
        with torch.no_grad():
            smooth = torch.full_like(log_probs, self.epsilon / (self.num_classes - 1))
            smooth.scatter_(1, targets.unsqueeze(1), 1.0 - self.epsilon)
        return (-smooth * log_probs).sum(dim=-1).mean()


def build_main_criterion(kind: str, **kw) -> nn.Module:
    kind = (kind or "focal").lower()
    if kind == "focal":
        return FocalLoss(gamma=kw.get("focal_gamma", 2.0), alpha=kw.get("focal_alpha", 0.25))
    if kind == "label_smoothing":
        return LabelSmoothingLoss(epsilon=kw.get("label_smoothing_eps", 0.1))
    if kind == "ce":
        return nn.CrossEntropyLoss()
    raise ValueError(f"未知 loss 类型 {kind!r}")


def rdrop_kl(logits1: torch.Tensor, logits2: torch.Tensor) -> torch.Tensor:
    """R-Drop（Liang 2021）双向 KL；两次 forward 因 dropout 不同得到两组 logits。"""
    p1 = F.log_softmax(logits1, dim=-1)
    p2 = F.log_softmax(logits2, dim=-1)
    return 0.5 * (
        F.kl_div(p1, p2.exp(), reduction="batchmean") + F.kl_div(p2, p1.exp(), reduction="batchmean")
    )


class SupConLoss(nn.Module):
    """监督对比（Khosla 2020）：同标签样本表示拉近、异标签推远。作用在融合向量上。"""

    def __init__(self, temperature: float = 0.07) -> None:
        super().__init__()
        self.temperature = temperature

    def forward(self, emb: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        n = emb.shape[0]
        if n < 2:
            return emb.new_zeros(())
        z = F.normalize(emb.float(), dim=1)
        sim = z @ z.t() / self.temperature
        # 数值稳定：减每行最大值
        sim = sim - sim.max(dim=1, keepdim=True).values.detach()
        self_mask = torch.eye(n, dtype=torch.bool, device=emb.device)
        pos_mask = (labels.unsqueeze(0) == labels.unsqueeze(1)) & ~self_mask
        exp_sim = torch.exp(sim).masked_fill(self_mask, 0.0)
        denom = exp_sim.sum(dim=1)
        pos = (exp_sim * pos_mask).sum(dim=1)
        valid = pos > 0
        if not valid.any():
            return emb.new_zeros(())
        return -torch.log(pos[valid] / denom[valid]).mean()
