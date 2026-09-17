"""
中文文本 AIGC 检测器微调脚本 (v2 — 全面优化版)

训练策略:
  1. Focal Loss (γ=2) — 聚焦难分类样本
  2. R-Drop — 两次 forward KL 一致性正则
  3. EMA — 指数移动平均权重
  4. FGM 对抗训练 — embedding 梯度扰动
  5. 多任务学习 — 主任务(AIGC) + 辅助任务(领域分类)
  6. 数据增强 — 同义词替换/回译模拟/句子打乱
  7. 分层学习率 — 底层/顶层/分类头不同 LR
  8. Label Smoothing — 防止过拟合
  9. 梯度累积 — 等效更大 batch

用法:
  python train_text_detector.py --epochs 5 --use_focal --use_ema --use_fgm
  python train_text_detector.py --help  # 查看所有选项
"""

import os
import sys
import argparse
import copy
import math
import random
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModel, get_cosine_schedule_with_warmup
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

random.seed(42)
torch.manual_seed(42)

# ============================================================
# 1. Loss 函数
# ============================================================

class FocalLoss(nn.Module):
    """Focal Loss — 自动聚焦难分类样本，减少易分类样本的梯度贡献"""
    def __init__(self, gamma: float = 2.0, alpha: float = 0.25, reduction: str = "mean"):
        super().__init__()
        self.gamma = gamma
        self.alpha = alpha
        self.reduction = reduction

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce = F.cross_entropy(logits, targets, reduction="none")
        pt = torch.exp(-ce)
        focal = self.alpha * (1 - pt) ** self.gamma * ce
        if self.reduction == "mean":
            return focal.mean()
        return focal.sum()


class LabelSmoothingLoss(nn.Module):
    """Label Smoothing CrossEntropy"""
    def __init__(self, epsilon: float = 0.1, num_classes: int = 2):
        super().__init__()
        self.epsilon = epsilon
        self.num_classes = num_classes

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        log_probs = F.log_softmax(logits, dim=-1)
        with torch.no_grad():
            smooth = torch.zeros_like(log_probs)
            smooth.fill_(self.epsilon / (self.num_classes - 1))
            smooth.scatter_(1, targets.unsqueeze(1), 1.0 - self.epsilon)
        return (-smooth * log_probs).sum(dim=-1).mean()


# ============================================================
# 2. 数据集 (含数据增强)
# ============================================================

# 内建回退样本
HUMAN_SAMPLES = [
    "今天上课讲到了二战历史，老师让我们每人写一篇关于诺曼底登陆的分析。我查了好多资料，看得头都大了。不过说实话，这场战役确实挺有意思的。",
    "刚才和同桌讨论了一下数学作业的最后一道大题，我俩想了半小时都没想出来。后来去问了课代表，他一讲我们才恍然大悟——原来要用辅助线法。",
    "下午在图书馆自习，旁边坐了一对情侣一直在讲话，烦死了。我戴着耳机都挡不住，只好搬到另一个角落。",
    "本报记者从市交通局获悉，地铁三号线北延段将于下月正式通车。该线路全长15.3公里，设车站12座。",
    "昨晚的暴雨导致老城区多处积水，最深达半米。消防部门连夜出动抽水车12辆，转移被困群众200余人。",
    "刚把代码部署到服务器上就崩了，看了半天日志才发现是一个拼写错误——变量名少打了个下划线。",
    "最近在学Rust，感觉相比Python确实严格很多。光是一个所有权系统就研究了三天。",
    "秋天的傍晚总是让人感到一丝忧伤。树叶黄了，风也凉了，街上的人裹紧了外套匆匆走过。",
]
AI_SAMPLES_GPT = [
    "通过本课程的学习，我们可以系统地掌握数据结构与算法的核心知识体系。值得注意的是，二叉树遍历的递归实现是理解更复杂数据结构的基础。",
    "本研究采用定量分析方法，对近年来中国高等教育的改革成效进行了全面评估。值得注意的是，研究发现双一流建设的实施显著提升了重点高校的科研产出能力。",
    "随着数字经济的快速发展，人工智能技术在各个行业的应用日益广泛。值得注意的是，AI在医疗领域的应用表现尤为突出。",
    "深度学习框架的选择对于模型开发的效率具有重要影响。PyTorch凭借其动态计算图的优势，在研究领域占据了主导地位。",
    "阳光透过树叶的缝隙洒落在地面上，形成斑驳的光影。微风吹过，带来了远处花草的清香。综上所述，生活中的小确幸往往就隐藏在这些平凡的瞬间之中。",
]
AI_SAMPLES_CLAUDE = [
    "我想谈谈我对这个问题的理解。首先，我们需要明确问题的边界条件。其次，在分析过程中，我注意到几点关键的制约因素。",
    "坦率地说，这是一个非常有趣的问题。让我尝试从几个不同的角度进行分析。一方面，我们需要考虑技术可行性的维度。",
]

# 数据增强: 中文同义词映射
SYNONYM_MAP = {
    "非常": "十分", "十分": "非常", "重要": "关键", "关键": "重要",
    "显著": "明显", "明显": "显著", "应用": "运用", "运用": "应用",
    "发展": "进步", "进步": "发展", "问题": "议题", "议题": "问题",
    "需要": "需求", "需求": "需要", "可以": "能够", "能够": "可以",
    "进行": "展开", "展开": "进行", "通过": "借助", "借助": "通过",
    "分析": "剖析", "剖析": "分析", "方法": "方式", "方式": "方法",
    "提升": "提高", "提高": "提升", "研究": "探讨", "探讨": "研究",
    "实现": "达成", "达成": "实现", "影响": "作用", "作用": "影响",
}


class ChineseAIGCDataset(Dataset):
    """中文 AIGC 检测数据集 — 支持多键文本、领域标注、数据增强"""

    @staticmethod
    def _get_text(item: dict) -> str:
        return item.get("text") or item.get("AI_text") or item.get("human_text") or ""

    def __init__(self, tokenizer, json_path: str | list[str] = None,
                 max_length: int = 512, max_samples: int = None,
                 augment: bool = False):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.augment = augment
        self.samples: list[tuple[str, int, str]] = []

        paths = json_path if isinstance(json_path, list) else [json_path]
        loaded = False

        for path in paths:
            if path and os.path.exists(path):
                import json
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if max_samples:
                    data = data[:max_samples]
                for item in data:
                    text = self._get_text(item)
                    label = item.get("label", 0)
                    domain = item.get("domain", "unknown")
                    if len(text) > 20:
                        self.samples.append((text[:max_length * 4], label, domain))
                loaded = True

        if not loaded:
            for text in HUMAN_SAMPLES:
                self.samples.append((text, 0, "builtin"))
            for text in AI_SAMPLES_GPT:
                self.samples.append((text, 1, "builtin"))
            for text in AI_SAMPLES_CLAUDE:
                self.samples.append((text, 1, "builtin"))

        random.shuffle(self.samples)

    def _augment_text(self, text: str) -> str:
        """随机数据增强"""
        if not self.augment or random.random() > 0.4:
            return text

        choice = random.random()
        # 同义词替换 (15% 概率)
        if choice < 0.375:
            words = list(text)
            for i, ch in enumerate(words):
                if ch in SYNONYM_MAP and random.random() < 0.15:
                    words[i] = SYNONYM_MAP[ch]
            return "".join(words)
        # 句子打乱 (10% 概率)
        elif choice < 0.625:
            sents = text.replace("。", "。<SPLIT>").replace("？", "?<SPLIT>").replace("！", "!<SPLIT>")
            parts = [p.strip() for p in sents.split("<SPLIT>") if p.strip()]
            if len(parts) >= 3:
                i, j = random.sample(range(len(parts)), 2)
                parts[i], parts[j] = parts[j], parts[i]
            return "。".join(parts) + ("。" if not parts[-1].endswith("。") else "")
        # 随机删除 (5% 概率)
        else:
            chars = list(text)
            keep = [c for c in chars if random.random() > 0.1]
            return "".join(keep) if len(keep) >= 20 else text

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        text, label, domain = self.samples[idx]
        text = self._augment_text(text)
        encoding = self.tokenizer(
            text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "label": torch.tensor(label, dtype=torch.long),
            "domain": domain,
            "text": text,
        }


# ============================================================
# 3. 梯度反转层 + 分类模型
# ============================================================

class GradientReversalLayer(torch.autograd.Function):
    """梯度反转层 (Gradient Reversal Layer, GRL)
    前向传播: 恒等映射
    反向传播: 梯度乘以 -lambda, 惩罚模型学会领域特征
    """

    @staticmethod
    def forward(ctx, x, lambda_=1.0):
        ctx.lambda_ = lambda_
        return x.view_as(x)

    @staticmethod
    def backward(ctx, grad_output):
        return grad_output.neg() * ctx.lambda_, None


class SupConLoss(nn.Module):
    """监督对比损失 (Supervised Contrastive Loss)
    同标签样本的 CLS 向量拉近, 异标签推远 — 增强特征区分度
    """

    def __init__(self, temperature: float = 0.07):
        super().__init__()
        self.temperature = temperature

    def forward(self, embeddings: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        # embeddings: [N, D], labels: [N]
        device = embeddings.device
        N = embeddings.shape[0]
        if N < 2:
            return torch.tensor(0.0, device=device, requires_grad=True)

        # 归一化
        embeddings = F.normalize(embeddings, dim=1)
        # 相似度矩阵 [N, N]
        sim = torch.mm(embeddings, embeddings.t()) / self.temperature
        # 标签掩码: 同标签=1
        label_mask = labels.unsqueeze(0) == labels.unsqueeze(1)
        # 排除自身
        self_mask = torch.eye(N, dtype=torch.bool, device=device)
        label_mask = label_mask & ~self_mask

        # 计算对比损失
        exp_sim = torch.exp(sim)
        pos_sum = (exp_sim * label_mask.float()).sum(dim=1)
        all_sum = exp_sim.sum(dim=1) - torch.diag(exp_sim)

        # 跳过没有正样本的
        valid = pos_sum > 0
        if not valid.any():
            return torch.tensor(0.0, device=device, requires_grad=True)

        loss = -torch.log(pos_sum[valid] / all_sum[valid]).mean()
        return loss


class RobertaAIGCDetector(nn.Module):
    """RoBERTa + 分类头 + 领域对抗(GRL) + 可选多任务"""

    def __init__(self, model_path: str, num_classes: int = 2, num_domains: int = 0,
                 use_grl: bool = False):
        super().__init__()
        self.roberta = AutoModel.from_pretrained(model_path, trust_remote_code=True, local_files_only=True)
        hidden = self.roberta.config.hidden_size
        self.hidden_size = hidden
        self.classifier = nn.Sequential(
            nn.Dropout(0.1),
            nn.Linear(hidden, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, num_classes),
        )
        self.num_domains = num_domains
        self.use_grl = use_grl
        if num_domains > 0:
            self.domain_classifier = nn.Sequential(
                nn.Dropout(0.1),
                nn.Linear(hidden, 128),
                nn.ReLU(),
                nn.Linear(128, num_domains),
            )

    def forward(self, input_ids, attention_mask, return_domain: bool = False,
                grl_lambda: float = 1.0):
        outputs = self.roberta(input_ids=input_ids, attention_mask=attention_mask)
        cls_emb = outputs.last_hidden_state[:, 0, :]
        logits = self.classifier(cls_emb)

        if return_domain and self.num_domains > 0:
            if self.use_grl:
                # GRL: 反转梯度, 惩罚模型学会领域特征
                reversed_emb = GradientReversalLayer.apply(cls_emb, grl_lambda)
                domain_logits = self.domain_classifier(reversed_emb)
            else:
                domain_logits = self.domain_classifier(cls_emb)
            return logits, domain_logits, cls_emb
        return logits


# ============================================================
# 4. EMA (指数移动平均)
# ============================================================

class EMA:
    """Exponential Moving Average of model parameters"""
    def __init__(self, model: nn.Module, decay: float = 0.999):
        self.model = model
        self.decay = decay
        self.shadow = {}
        self.backup = {}
        self._register()

    def _register(self):
        for name, param in self.model.named_parameters():
            if param.requires_grad:
                self.shadow[name] = param.data.clone()

    def update(self):
        for name, param in self.model.named_parameters():
            if param.requires_grad:
                self.shadow[name] = self.decay * self.shadow[name] + (1.0 - self.decay) * param.data

    def apply_shadow(self):
        """推理前用 EMA 权重替换模型权重"""
        for name, param in self.model.named_parameters():
            if param.requires_grad:
                self.backup[name] = param.data.clone()
                param.data = self.shadow[name]

    def restore(self):
        """推理后恢复原始权重 (继续训练)"""
        for name, param in self.model.named_parameters():
            if param.requires_grad:
                param.data = self.backup[name]
        self.backup.clear()


# ============================================================
# 5. FGM 对抗训练
# ============================================================

class FGM:
    """Fast Gradient Method — embedding 层对抗扰动"""
    def __init__(self, model: nn.Module, epsilon: float = 0.5):
        self.model = model
        self.epsilon = epsilon
        self.backup = {}

    def attack(self):
        """对 embedding 施加扰动"""
        for name, param in self.model.named_parameters():
            if param.requires_grad and "embeddings" in name:
                self.backup[name] = param.data.clone()
                norm = param.grad.norm()
                if norm > 0 and not torch.isnan(norm):
                    r_at = self.epsilon * param.grad / norm
                    param.data.add_(r_at)

    def restore(self):
        """恢复原始 embedding"""
        for name, param in self.model.named_parameters():
            if name in self.backup:
                param.data = self.backup[name]
        self.backup.clear()


# ============================================================
# 6. 训练
# ============================================================

def build_domain_map(train_json) -> dict[str, int]:
    """从训练数据构建 domain → id 映射。"""
    import json as _json
    domain_set = set()
    paths = train_json if isinstance(train_json, list) else [train_json]
    for path in paths:
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = _json.load(f)
            for item in data[:5000]:  # 前 5000 条即可
                d = item.get("domain", "unknown")
                domain_set.add(d)
    return {d: i for i, d in enumerate(sorted(domain_set))}


def train_text_detector(
    model_path: str = "hfl/chinese-roberta-wwm-ext",
    train_json: str | list[str] = "../data/training/aigc_diverse_train.json",
    val_json: str | list[str] = "../data/training/aigc_diverse_val.json",
    epochs: int = 5,
    batch_size: int = 16,
    lr: float = 2e-5,
    max_samples: int = 60000,
    max_length: int = 512,
    unfreeze_layers: int = 8,
    save_path: str = "../models/text/aigc_detector.pth",
    # 优化策略开关
    use_focal: bool = True,
    use_label_smoothing: bool = False,  # focal 和 label_smooth 二选一
    use_rdrop: bool = True,
    rdrop_alpha: float = 0.5,
    use_ema: bool = True,
    ema_decay: float = 0.999,
    use_fgm: bool = True,
    fgm_epsilon: float = 0.5,
    use_multitask: bool = True,
    multitask_weight: float = 0.3,
    use_augment: bool = True,
    grad_accum_steps: int = 2,
    # 分层学习率
    layerwise_lr: bool = True,
    bottom_lr_factor: float = 0.25,
    head_lr_factor: float = 5.0,
    # 领域对抗 + 对比学习 (论文检测核心)
    use_grl: bool = False,
    grl_lambda: float = 0.5,
    use_contrastive: bool = False,
    contrastive_weight: float = 0.1,
    contrastive_temperature: float = 0.07,
):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True, local_files_only=True)

    # Dataset
    train_ds = ChineseAIGCDataset(tokenizer, train_json, max_length=max_length,
                                  max_samples=max_samples, augment=use_augment)
    val_ds = ChineseAIGCDataset(tokenizer, val_json, max_length=max_length,
                                max_samples=max_samples // 4, augment=False)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,
                              num_workers=2, pin_memory=True, drop_last=use_rdrop)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False,
                            num_workers=2, pin_memory=True)

    print(f"\nDataset: {len(train_ds)} train, {len(val_ds)} val samples")

    # Domain map for multi-task
    num_domains = 0
    domain_map = {}
    if use_multitask:
        domain_map = build_domain_map(train_json)
        num_domains = len(domain_map)
        print(f"Domains: {num_domains} — {list(domain_map.keys())}")

    # Model
    model = RobertaAIGCDetector(model_path, num_domains=num_domains, use_grl=use_grl).to(device)
    print(f"Model: {sum(p.numel() for p in model.parameters()) / 1e6:.1f}M params")

    # 冻结底层
    num_encoder_layers = len(model.roberta.encoder.layer)
    frozen_layers = num_encoder_layers - unfreeze_layers
    for param in model.roberta.embeddings.parameters():
        param.requires_grad = False
    for i, layer in enumerate(model.roberta.encoder.layer):
        if i < frozen_layers:
            for param in layer.parameters():
                param.requires_grad = False

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Trainable: {trainable / 1e6:.1f}M params (frozen={frozen_layers}/{num_encoder_layers} layers)")

    # 分层学习率
    if layerwise_lr:
        bottom_params = []
        mid_params = []
        top_params = []
        head_params = []

        for name, param in model.named_parameters():
            if not param.requires_grad:
                continue
            if "roberta.embeddings" in name:
                bottom_params.append(param)
            elif "roberta.encoder.layer" in name:
                layer_num = int(name.split("encoder.layer.")[1].split(".")[0])
                if layer_num < num_encoder_layers // 2:
                    bottom_params.append(param)
                elif layer_num < num_encoder_layers - 2:
                    mid_params.append(param)
                else:
                    top_params.append(param)
            else:
                head_params.append(param)

        optimizer = torch.optim.AdamW([
            {"params": bottom_params, "lr": lr * bottom_lr_factor},
            {"params": mid_params, "lr": lr * 0.5},
            {"params": top_params, "lr": lr},
            {"params": head_params, "lr": lr * head_lr_factor},
        ], weight_decay=0.01)
        print(f"Layer-wise LR: bottom={lr*bottom_lr_factor:.1e}, mid={lr*0.5:.1e}, top={lr:.1e}, head={lr*head_lr_factor:.1e}")
    else:
        optimizer = torch.optim.AdamW(
            filter(lambda p: p.requires_grad, model.parameters()),
            lr=lr, weight_decay=0.01,
        )

    total_steps = len(train_loader) * epochs // grad_accum_steps
    scheduler = get_cosine_schedule_with_warmup(optimizer, num_warmup_steps=total_steps // 10, num_training_steps=total_steps)

    # Loss
    if use_focal:
        criterion = FocalLoss(gamma=2.0)
        print("Loss: FocalLoss (gamma=2.0)")
    elif use_label_smoothing:
        criterion = LabelSmoothingLoss(epsilon=0.1)
        print("Loss: LabelSmoothing (epsilon=0.1)")
    else:
        criterion = nn.CrossEntropyLoss()
        print("Loss: CrossEntropyLoss")
    domain_criterion = nn.CrossEntropyLoss()

    # 对比学习
    contrastive_criterion = SupConLoss(temperature=contrastive_temperature) if use_contrastive else None
    if use_contrastive:
        print(f"Contrastive: SupConLoss (temperature={contrastive_temperature}, weight={contrastive_weight})")
    if use_grl:
        print(f"GRL: domain adversarial (lambda={grl_lambda})")

    # EMA
    ema = EMA(model, decay=ema_decay) if use_ema else None
    if ema:
        print(f"EMA: decay={ema_decay}")

    # FGM
    fgm = FGM(model, epsilon=fgm_epsilon) if use_fgm else None
    if fgm:
        print(f"FGM: epsilon={fgm_epsilon}")

    if use_rdrop:
        print(f"R-Drop: alpha={rdrop_alpha}")
    if use_multitask and num_domains > 0:
        print(f"Multi-task: {num_domains} domains, weight={multitask_weight}")
    if use_augment:
        print("Data Augmentation: enabled")
    if grad_accum_steps > 1:
        print(f"Gradient Accumulation: {grad_accum_steps} steps (effective batch={batch_size * grad_accum_steps})")

    best_val_acc = 0.0
    best_val_f1 = 0.0
    print("-" * 60)

    for epoch in range(epochs):
        # === Train ===
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0
        optimizer.zero_grad()

        pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs}")
        for step, batch in enumerate(pbar):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["label"].to(device)

            # R-Drop: 两次 forward
            if use_rdrop:
                need_cls = use_contrastive or (use_grl and num_domains > 0)
                if (use_multitask or use_grl) and num_domains > 0:
                    logits1, domain_logits1, cls1 = model(input_ids, attention_mask,
                        return_domain=True, grl_lambda=grl_lambda)
                    logits2, domain_logits2, cls2 = model(input_ids, attention_mask,
                        return_domain=True, grl_lambda=grl_lambda)
                else:
                    logits1 = model(input_ids, attention_mask)
                    logits2 = model(input_ids, attention_mask)

                loss_main = criterion(logits1, labels) + criterion(logits2, labels)
                kl1 = F.kl_div(F.log_softmax(logits1, -1), F.softmax(logits2, -1), reduction="batchmean")
                kl2 = F.kl_div(F.log_softmax(logits2, -1), F.softmax(logits1, -1), reduction="batchmean")
                loss = (loss_main + rdrop_alpha * (kl1 + kl2)) / 2

                if (use_multitask or use_grl) and num_domains > 0:
                    domain_ids = torch.tensor(
                        [domain_map.get(batch["domain"][j], 0) for j in range(len(labels))], device=device
                    )
                    loss_domain = domain_criterion(domain_logits1, domain_ids) + domain_criterion(domain_logits2, domain_ids)
                    loss = loss + multitask_weight * loss_domain / 2

                # 对比学习
                if use_contrastive and need_cls:
                    cls_avg = (cls1 + cls2) / 2
                    loss_contrast = contrastive_criterion(cls_avg, labels)
                    loss = loss + contrastive_weight * loss_contrast

                preds = logits1.argmax(dim=-1)
            else:
                need_cls = use_contrastive or (use_grl and num_domains > 0)
                if (use_multitask or use_grl) and num_domains > 0:
                    logits, domain_logits, cls_emb = model(input_ids, attention_mask,
                        return_domain=True, grl_lambda=grl_lambda)
                else:
                    logits = model(input_ids, attention_mask)

                loss = criterion(logits, labels)

                if (use_multitask or use_grl) and num_domains > 0:
                    domain_ids = torch.tensor(
                        [domain_map.get(batch["domain"][j], 0) for j in range(len(labels))], device=device
                    )
                    loss_domain = domain_criterion(domain_logits, domain_ids)
                    loss = loss + multitask_weight * loss_domain

                # 对比学习
                if use_contrastive and need_cls:
                    loss_contrast = contrastive_criterion(cls_emb, labels)
                    loss = loss + contrastive_weight * loss_contrast

                preds = logits.argmax(dim=-1)

            loss = loss / grad_accum_steps
            loss.backward()

            # FGM 对抗训练
            if use_fgm and (step % 2 == 0):
                fgm.attack()
                if use_multitask and num_domains > 0:
                    logits_adv, _, _ = model(input_ids, attention_mask, return_domain=True)
                else:
                    logits_adv = model(input_ids, attention_mask)
                loss_adv = criterion(logits_adv, labels) / grad_accum_steps
                loss_adv.backward()
                fgm.restore()

            if (step + 1) % grad_accum_steps == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                if ema:
                    ema.update()

            train_loss += loss.item() * grad_accum_steps
            train_correct += (preds == labels).sum().item()
            train_total += labels.size(0)

            pbar.set_postfix({
                "loss": f"{loss.item() * grad_accum_steps:.4f}",
                "acc": f"{train_correct / train_total:.3f}"
            })

        train_acc = train_correct / train_total

        # === Val (使用 EMA 权重) ===
        if ema:
            ema.apply_shadow()

        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        val_logits_list = []
        val_labels_list = []
        domain_correct: dict[str, int] = {}
        domain_total: dict[str, int] = {}

        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                labels = batch["label"].to(device)

                if use_multitask and num_domains > 0:
                    logits, _, _ = model(input_ids, attention_mask, return_domain=True)
                else:
                    logits = model(input_ids, attention_mask)

                loss = criterion(logits, labels)
                val_loss += loss.item()
                preds = logits.argmax(dim=-1)
                val_correct += (preds == labels).sum().item()
                val_total += labels.size(0)

                val_logits_list.extend(logits[:, 1].cpu().numpy().tolist())
                val_labels_list.extend(labels.cpu().numpy().tolist())

                domains = batch["domain"]
                for j in range(len(labels)):
                    d = domains[j]
                    domain_total[d] = domain_total.get(d, 0) + 1
                    if preds[j] == labels[j]:
                        domain_correct[d] = domain_correct.get(d, 0) + 1

        val_acc = val_correct / val_total

        # 恢复原始权重 (如果需要继续训练)
        if ema:
            ema.restore()

        # Calibration
        from app.services.calibration import ConfidenceCalibrator
        calibrator = ConfidenceCalibrator()
        T = calibrator.fit_temperature(np.array(val_logits_list), np.array(val_labels_list))
        a, b = calibrator.fit_platt(np.array(val_logits_list) / max(T, 0.1), np.array(val_labels_list))
        ece = calibrator.compute_ece(
            1 / (1 + np.exp(-np.array(val_logits_list))),
            np.array(val_labels_list),
        )

        # F1
        val_preds_binary = (np.array(val_logits_list) > 0).astype(int)
        val_labels_arr = np.array(val_labels_list)
        tp = ((val_preds_binary == 1) & (val_labels_arr == 1)).sum()
        fp = ((val_preds_binary == 1) & (val_labels_arr == 0)).sum()
        fn = ((val_preds_binary == 0) & (val_labels_arr == 1)).sum()
        precision = tp / (tp + fp + 1e-8)
        recall = tp / (tp + fn + 1e-8)
        f1 = 2 * precision * recall / (precision + recall + 1e-8)

        print(f"\n  Train: loss={train_loss/len(train_loader):.4f} acc={train_acc:.4f}")
        print(f"  Val:   loss={val_loss/len(val_loader):.4f} acc={val_acc:.4f} F1={f1:.4f} ECE={ece:.4f}")
        print(f"  Calib: T={T:.3f} Platt=({a:.3f},{b:.3f})")

        # Per-domain
        if len(domain_total) > 2:
            print(f"  Per-domain:")
            for d in sorted(domain_total, key=lambda x: -domain_total[x])[:8]:
                d_acc = domain_correct.get(d, 0) / max(domain_total[d], 1)
                print(f"    {d:15s}: acc={d_acc:.3f}  n={domain_total[d]}")

        # Save best
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_val_f1 = f1

            # Save with EMA weights
            if ema:
                ema.apply_shadow()

            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            domain_summary = {
                d: {"total": domain_total[d], "acc": domain_correct.get(d, 0) / max(domain_total[d], 1)}
                for d in domain_total
            }
            torch.save({
                "model_state_dict": {k: v.cpu() for k, v in model.state_dict().items()},
                "classifier_state_dict": {k: v.cpu() for k, v in model.classifier.state_dict().items()},
                "temperature": T,
                "platt_a": a,
                "platt_b": b,
                "val_acc": val_acc,
                "val_f1": f1,
                "ece": ece,
                "domain_metrics": domain_summary,
                "domain_map": domain_map,
                "hyperparams": {
                    "epochs": epochs, "batch_size": batch_size, "lr": lr,
                    "max_length": max_length, "unfreeze_layers": unfreeze_layers,
                    "use_focal": use_focal, "use_rdrop": use_rdrop,
                    "use_ema": use_ema, "use_fgm": use_fgm,
                    "use_multitask": use_multitask, "num_domains": num_domains,
                },
            }, save_path)
            print(f"  -> Saved to {save_path}")

            if ema:
                ema.restore()

    print(f"\nBest: val_acc={best_val_acc:.4f} val_f1={best_val_f1:.4f}")
    return best_val_acc


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Chinese-RoBERTa AIGC Detection Training (v2 — Optimized)")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max_samples", type=int, default=60000)
    parser.add_argument("--max_length", type=int, default=512)
    parser.add_argument("--unfreeze_layers", type=int, default=8)
    parser.add_argument("--train_data", type=str, nargs="+",
                        default=["../data/training/aigc_diverse_train.json"])
    parser.add_argument("--val_data", type=str, nargs="+",
                        default=["../data/training/aigc_diverse_val.json"])
    parser.add_argument("--model_path", type=str, default="hfl/chinese-roberta-wwm-ext")
    parser.add_argument("--save_path", type=str, default="../models/text/aigc_detector.pth")
    # Optimization toggles
    parser.add_argument("--use_focal", action="store_true", default=True)
    parser.add_argument("--no_focal", action="store_true")
    parser.add_argument("--use_label_smoothing", action="store_true")
    parser.add_argument("--no_rdrop", action="store_true")
    parser.add_argument("--rdrop_alpha", type=float, default=0.5)
    parser.add_argument("--no_ema", action="store_true")
    parser.add_argument("--no_fgm", action="store_true")
    parser.add_argument("--no_multitask", action="store_true")
    parser.add_argument("--multitask_weight", type=float, default=0.3)
    parser.add_argument("--no_augment", action="store_true")
    parser.add_argument("--grad_accum_steps", type=int, default=2)
    parser.add_argument("--no_layerwise_lr", action="store_true")
    # 论文检测专属: 领域对抗 + 对比学习
    parser.add_argument("--use_grl", action="store_true", help="启用梯度反转层 (领域对抗训练)")
    parser.add_argument("--grl_lambda", type=float, default=0.5, help="GRL 梯度反转系数")
    parser.add_argument("--use_contrastive", action="store_true", help="启用监督对比学习 (SupCon)")
    parser.add_argument("--contrastive_weight", type=float, default=0.1, help="对比损失权重")
    parser.add_argument("--contrastive_temperature", type=float, default=0.07, help="对比损失温度")
    args = parser.parse_args()

    train_text_detector(
        model_path=args.model_path,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        max_samples=args.max_samples,
        max_length=args.max_length,
        unfreeze_layers=args.unfreeze_layers,
        train_json=args.train_data,
        val_json=args.val_data,
        save_path=args.save_path,
        use_focal=args.use_focal and not args.no_focal and not args.use_label_smoothing,
        use_label_smoothing=args.use_label_smoothing,
        use_rdrop=not args.no_rdrop,
        rdrop_alpha=args.rdrop_alpha,
        use_ema=not args.no_ema,
        use_fgm=not args.no_fgm,
        use_multitask=not args.no_multitask,
        multitask_weight=args.multitask_weight,
        use_augment=not args.no_augment,
        grad_accum_steps=args.grad_accum_steps,
        layerwise_lr=not args.no_layerwise_lr,
        use_grl=args.use_grl,
        grl_lambda=args.grl_lambda,
        use_contrastive=args.use_contrastive,
        contrastive_weight=args.contrastive_weight,
        contrastive_temperature=args.contrastive_temperature,
    )


if __name__ == "__main__":
    main()
