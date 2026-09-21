"""
文本 AIGC 检测训练入口
======================

用法::

    python -m ml.training.text.train --config ml/configs/text/v0.2.0-fusion-mdeberta.yaml
    python -m ml.training.text.train --config ... --max-train-samples 2000 --epochs 1   # 冒烟

产出（output.checkpoint_dir）::

    best.pth              见 ml/common/checkpoint.py 的 schema，推理服务直接加载
    metrics.json          val / test 指标 + 分场景 / 分增强类型细分
    config.snapshot.yaml  本次训练配置快照（可复现）

训练流程：
  yaml → 采样（场景均衡 + 改写/润色配比）→ 表层特征 scaler 拟合 → 模型（fusion / cls_only）
  → 解冻策略 + 分层 LR → AdamW + cosine warmup → [Focal + R-Drop + FGM + EMA + 溯源多任务 + SupCon]
  → 每 epoch（或 eval_every_steps）在 val 上算 AUROC / F1 → 早停
  → 最优权重上拟合 温度 + Platt → 低假阳阈值 → 落盘
"""
from __future__ import annotations

import argparse
import contextlib
import json
import logging
import math
import os
import shutil
import time
from collections import defaultdict

import numpy as np
import torch
import torch.nn as nn
import yaml
from torch.utils.data import DataLoader
from transformers import AutoTokenizer, get_cosine_schedule_with_warmup

from ml.common.checkpoint import save_checkpoint
from ml.common.fusion_model import ARCH_FUSION, FusionAIGCDetector, freeze_backbone_except_last
from ml.common.surface_features import SURFACE_DIM, SURFACE_FEATURE_VERSION, SurfaceScaler
from ml.datasets.text.schema import SOURCE_FAMILIES
from ml.training.text.calibration import (
    auroc, binary_metrics, calibrate, find_thresholds, tpr_at_fpr,
)
from ml.training.text.data import (
    TextAIGCDataset, augment_mix_sampler, build_collate, fit_surface_scaler,
    load_jsonl, scenario_balanced_sampler,
)
from ml.training.text.losses import SupConLoss, build_main_criterion, rdrop_kl
from ml.training.text.tricks import EMA, FGM, build_param_groups, set_seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")
log = logging.getLogger("train")


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _autocast(precision: str, device: torch.device):
    if device.type != "cuda" or precision == "fp32":
        return contextlib.nullcontext()
    dtype = torch.bfloat16 if precision == "bf16" else torch.float16
    return torch.autocast(device_type="cuda", dtype=dtype)


# ---------------------------------------------------------------------------
# 评估
# ---------------------------------------------------------------------------

@torch.no_grad()
def evaluate(model: FusionAIGCDetector, loader: DataLoader, device: torch.device, precision: str,
             use_surface: bool) -> dict:
    """返回 raw logits（logits[:,1]，与推理侧口径一致）、labels 及分组信息，指标由调用方算。"""
    model.eval()
    logits_all, labels_all, scen_all, aug_all = [], [], [], []
    for batch in loader:
        ids = batch["input_ids"].to(device, non_blocking=True)
        mask = batch["attention_mask"].to(device, non_blocking=True)
        surf = batch["surface"].to(device, non_blocking=True) if use_surface else None
        with _autocast(precision, device):
            logits = model(ids, mask, surface=surf)
        logits_all.append(logits[:, 1].float().cpu().numpy())
        labels_all.append(batch["label"].numpy())
        scen_all.extend(batch["scenario"])
        aug_all.extend(batch["augment"])
    return {
        "logits": np.concatenate(logits_all) if logits_all else np.zeros(0),
        "labels": np.concatenate(labels_all) if labels_all else np.zeros(0, dtype=int),
        "scenario": scen_all,
        "augment": aug_all,
    }


def summarize(ev: dict, probs: np.ndarray | None = None, threshold: float = 0.5) -> dict:
    """ev 来自 evaluate()；probs 为空时用 sigmoid(logit) 粗算。分场景 / 分增强类型细分。"""
    logits, labels = ev["logits"], ev["labels"]
    if len(labels) == 0:
        return {}
    if probs is None:
        probs = 1.0 / (1.0 + np.exp(-logits))
    out = binary_metrics(probs, labels, threshold)
    out["auroc"] = auroc(logits, labels)
    for t in (0.01, 0.05):
        tpr, _ = tpr_at_fpr(logits, labels, t)
        out[f"tpr_at_fpr_{int(t * 100)}pct"] = tpr
    groups: dict[str, dict[str, list[int]]] = {"scenario": defaultdict(list), "augment": defaultdict(list)}
    for i, (sc, ag) in enumerate(zip(ev["scenario"], ev["augment"])):
        groups["scenario"][sc].append(i)
        groups["augment"][ag].append(i)
    for gname, gmap in groups.items():
        out[f"by_{gname}"] = {}
        for key, idx in sorted(gmap.items()):
            idx = np.asarray(idx)
            m = binary_metrics(probs[idx], labels[idx], threshold)
            m["n"] = int(len(idx))
            if labels[idx].min() != labels[idx].max():
                m["auroc"] = auroc(logits[idx], labels[idx])
            out[f"by_{gname}"][key] = m
    return out


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def train(cfg: dict, max_train_samples: int | None = None, epochs_override: int | None = None,
          dry_run: bool = False) -> dict:
    mcfg, dcfg, tcfg = cfg["model"], cfg["data"], cfg["train"]
    ccfg, ocfg, mlf = cfg.get("calibration", {}), cfg["output"], cfg.get("mlflow", {})
    set_seed(int(tcfg.get("seed", 42)))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    precision = str(tcfg.get("precision", "bf16")).lower()
    if device.type == "cuda" and precision == "bf16" and not torch.cuda.is_bf16_supported():
        precision = "fp16"
    log.info("device=%s precision=%s", device, precision)

    arch = mcfg.get("arch", ARCH_FUSION)
    use_surface = arch == ARCH_FUSION
    num_sources = len(SOURCE_FAMILIES) if mcfg.get("use_source_head") else 0
    epochs = int(epochs_override or tcfg["epochs"])

    # ---- 数据
    min_chars = int(dcfg.get("min_chars", 120))
    train_raw = load_jsonl(dcfg["train_jsonl"], min_chars=min_chars)
    val_raw = load_jsonl(dcfg["val_jsonl"], min_chars=min_chars)
    log.info("raw train=%d val=%d", len(train_raw), len(val_raw))
    if dcfg.get("augment_mix"):
        train_raw = augment_mix_sampler(train_raw, dcfg["augment_mix"], seed=int(tcfg.get("seed", 42)))
    train_samples = scenario_balanced_sampler(
        train_raw, dcfg.get("scenario_mix", {}), total=dcfg.get("train_total"), seed=int(tcfg.get("seed", 42)),
    )
    if max_train_samples:
        train_samples = train_samples[:max_train_samples]
        val_raw = val_raw[: max(200, max_train_samples // 5)]
    log.info("sampled train=%d val=%d", len(train_samples), len(val_raw))
    _log_distribution(train_samples)

    tokenizer = AutoTokenizer.from_pretrained(
        mcfg["backbone"], trust_remote_code=True,
        local_files_only=bool(mcfg.get("local_files_only")) or os.path.isdir(mcfg["backbone"]),
    )
    scaler = fit_surface_scaler(train_samples, seed=int(tcfg.get("seed", 42))) if use_surface else SurfaceScaler()

    oa = dcfg.get("online_augment", {}) or {}
    train_ds = TextAIGCDataset(
        train_samples, tokenizer, max_length=int(dcfg.get("max_length", 512)), scaler=scaler, use_surface=use_surface,
        augment_prob=float(oa.get("prob", 0.0)),
        augment_kw={k: float(v) for k, v in oa.items() if k.startswith("p_")},
        seed=int(tcfg.get("seed", 42)),
    )
    val_ds = TextAIGCDataset(val_raw, tokenizer, max_length=int(dcfg.get("max_length", 512)), scaler=scaler,
                             use_surface=use_surface, augment_prob=0.0)
    collate = build_collate(tokenizer.pad_token_id or 0)
    nw = int(dcfg.get("num_workers", 2))
    train_loader = DataLoader(train_ds, batch_size=int(tcfg["batch_size"]), shuffle=True, num_workers=nw,
                              pin_memory=device.type == "cuda", collate_fn=collate, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=int(tcfg["batch_size"]) * 2, shuffle=False, num_workers=nw,
                            pin_memory=device.type == "cuda", collate_fn=collate)

    # ---- 模型
    model = FusionAIGCDetector(
        backbone=mcfg["backbone"], arch=arch,
        classifier_hidden=int(mcfg.get("classifier_hidden", 256)), dropout=float(mcfg.get("dropout", 0.1)),
        cnn_kernels=tuple(mcfg.get("cnn_kernels", (2, 3, 5))), cnn_filters=int(mcfg.get("cnn_filters", 128)),
        surface_dim=SURFACE_DIM, surface_hidden=int(mcfg.get("surface_hidden", 64)),
        num_sources=num_sources, gradient_checkpointing=bool(mcfg.get("gradient_checkpointing")),
        local_files_only=bool(mcfg.get("local_files_only")) or os.path.isdir(mcfg["backbone"]),
    ).to(device)
    frozen, total_layers = freeze_backbone_except_last(model, int(tcfg.get("unfreeze_layers", 8)))
    n_train = sum(p.numel() for p in model.parameters() if p.requires_grad)
    log.info("arch=%s params=%.1fM trainable=%.1fM frozen_layers=%d/%d",
             arch, sum(p.numel() for p in model.parameters()) / 1e6, n_train / 1e6, frozen, total_layers)

    lw = tcfg.get("layerwise_lr") or {}
    groups = build_param_groups(
        model, lr=float(tcfg["lr"]), weight_decay=float(tcfg.get("weight_decay", 0.01)),
        bottom_factor=float(lw.get("bottom", 0.1)), mid_factor=float(lw.get("mid", 0.5)),
        head_factor=float(lw.get("head", 5.0)), n_layers=total_layers or None,
    )
    optimizer = torch.optim.AdamW(groups)
    accum = int(tcfg.get("grad_accum_steps", 1))
    total_steps = max(1, len(train_loader) * epochs // accum)
    scheduler = get_cosine_schedule_with_warmup(
        optimizer, int(total_steps * float(tcfg.get("warmup_ratio", 0.1))), total_steps
    )
    grad_scaler = torch.cuda.amp.GradScaler(enabled=(device.type == "cuda" and precision == "fp16"))

    criterion = build_main_criterion(tcfg.get("loss", "focal"), focal_gamma=float(tcfg.get("focal_gamma", 2.0)),
                                     focal_alpha=float(tcfg.get("focal_alpha", 0.25)),
                                     label_smoothing_eps=float(tcfg.get("label_smoothing_eps", 0.1)))
    source_criterion = nn.CrossEntropyLoss()
    rdrop_alpha = float(tcfg.get("rdrop_alpha", 0.0))
    src_w = float(tcfg.get("source_loss_weight", 0.0)) if num_sources else 0.0
    con_w = float(tcfg.get("contrastive_weight", 0.0))
    supcon = SupConLoss(float(tcfg.get("contrastive_temperature", 0.07))) if con_w > 0 else None
    ema = EMA(model, float(tcfg["ema_decay"])) if float(tcfg.get("ema_decay", 0)) > 0 else None
    fgm = FGM(model, float(tcfg["fgm_epsilon"])) if float(tcfg.get("fgm_epsilon", 0)) > 0 else None
    fgm_every = max(1, int(tcfg.get("fgm_every", 2)))

    # ---- MLflow（可选）
    mlrun = None
    if mlf.get("enabled") and not dry_run:
        try:
            import mlflow
            mlflow.set_tracking_uri(mlf.get("tracking_uri", "http://localhost:5000"))
            mlflow.set_experiment(mlf.get("experiment", "text_detector"))
            mlrun = mlflow.start_run(run_name=mlf.get("run_name", cfg.get("version")))
            mlflow.log_params({f"model.{k}": v for k, v in mcfg.items()})
            mlflow.log_params({f"train.{k}": v for k, v in tcfg.items() if not isinstance(v, dict)})
        except Exception as e:  # MLflow 不可用不阻塞训练
            log.warning("mlflow 不可用：%s", e)
            mlrun = None

    out_dir = ocfg["checkpoint_dir"]
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "config.snapshot.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)

    metric_key = tcfg.get("metric_for_best", "val_auroc").replace("val_", "")
    patience = int(tcfg.get("early_stop_patience", 2))
    eval_every = int(tcfg.get("eval_every_steps", 0))
    best_score, bad_epochs, best_metrics, global_step = -1.0, 0, {}, 0
    best_state_path = os.path.join(out_dir, "best.pth")
    t0 = time.time()

    def forward_loss(batch: dict) -> tuple[torch.Tensor, torch.Tensor]:
        ids = batch["input_ids"].to(device, non_blocking=True)
        mask = batch["attention_mask"].to(device, non_blocking=True)
        labels = batch["label"].to(device, non_blocking=True)
        surf = batch["surface"].to(device, non_blocking=True) if use_surface else None
        need_extra = bool(src_w or supcon)
        with _autocast(precision, device):
            if rdrop_alpha > 0:
                l1, s1, e1 = model(ids, mask, surf, return_source=need_extra, return_emb=need_extra)
                l2, s2, e2 = model(ids, mask, surf, return_source=need_extra, return_emb=need_extra)
                loss = 0.5 * (criterion(l1, labels) + criterion(l2, labels)) + rdrop_alpha * rdrop_kl(l1, l2)
                logits, src_logits, emb = l1, s1, (None if e1 is None else 0.5 * (e1 + e2))
                if src_w and s1 is not None:
                    sid = batch["source_id"].to(device)
                    loss = loss + src_w * 0.5 * (source_criterion(s1, sid) + source_criterion(s2, sid))
            else:
                logits, src_logits, emb = model(ids, mask, surf, return_source=need_extra, return_emb=need_extra)
                loss = criterion(logits, labels)
                if src_w and src_logits is not None:
                    loss = loss + src_w * source_criterion(src_logits, batch["source_id"].to(device))
            if supcon is not None and emb is not None:
                loss = loss + con_w * supcon(emb, labels)
        return loss, logits

    def run_eval_and_maybe_save(tag: str) -> dict:
        nonlocal best_score, bad_epochs, best_metrics
        if ema:
            ema.apply_shadow()
        ev = evaluate(model, val_loader, device, precision, use_surface)
        params, probs = calibrate(ev["logits"], ev["labels"], int(ccfg.get("temperature_max_iter", 200)),
                                  float(ccfg.get("platt_c", 1.0)))
        m = summarize(ev, probs)
        m["ece_before"], m["ece_after"] = params.ece_before, params.ece_after
        m["temperature"], m["platt_a"], m["platt_b"] = params.temperature, params.platt_a, params.platt_b
        score = float(m.get(metric_key, m.get("auroc", 0.0)))
        log.info("[%s] val auroc=%.4f f1=%.4f acc=%.4f tpr@fpr1=%.3f ece=%.4f→%.4f T=%.3f a=%.3f b=%.3f",
                 tag, m["auroc"], m["f1"], m["accuracy"], m["tpr_at_fpr_1pct"],
                 params.ece_before, params.ece_after, params.temperature, params.platt_a, params.platt_b)
        for key, gm in m.get("by_augment", {}).items():
            log.info("    augment=%-18s n=%-6d recall=%.3f f1=%.3f", key, gm["n"], gm["recall"], gm["f1"])
        if mlrun:
            import mlflow
            mlflow.log_metrics({f"val_{k}": v for k, v in m.items() if isinstance(v, (int, float)) and not math.isnan(v)},
                               step=global_step)
        if score > best_score:
            best_score, bad_epochs = score, 0
            thresholds = find_thresholds(probs, ev["labels"], tuple(ccfg.get("target_fprs", (0.01, 0.05))))
            best_metrics = {"val": m, "thresholds": thresholds, "best_step": global_step, "tag": tag}
            hparams = {
                "version": cfg.get("version"), "codename": cfg.get("codename"),
                "backbone": mcfg["backbone"], "arch": arch, "max_length": int(dcfg.get("max_length", 512)),
                "classifier_hidden": int(mcfg.get("classifier_hidden", 256)), "dropout": float(mcfg.get("dropout", 0.1)),
                "cnn_kernels": list(mcfg.get("cnn_kernels", (2, 3, 5))), "cnn_filters": int(mcfg.get("cnn_filters", 128)),
                "surface_hidden": int(mcfg.get("surface_hidden", 64)), "surface_dim": SURFACE_DIM,
                "surface_feature_version": SURFACE_FEATURE_VERSION, "surface_scaler": scaler.to_dict(),
                "num_sources": num_sources, "source_families": list(SOURCE_FAMILIES) if num_sources else [],
                "num_classes": 2, "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            if not dry_run:
                save_checkpoint(best_state_path, model, hparams, params.temperature, params.platt_a, params.platt_b,
                                thresholds, best_metrics)
                log.info("    -> saved %s (thresholds=%s)", best_state_path,
                         {k: round(v, 3) for k, v in thresholds.items()})
        else:
            bad_epochs += 1
        if ema:
            ema.restore()
        model.train()
        return m

    # ---- 训练循环
    model.train()
    stop = False
    for epoch in range(epochs):
        run_loss, run_correct, run_n = 0.0, 0, 0
        optimizer.zero_grad(set_to_none=True)
        for step, batch in enumerate(train_loader):
            loss, logits = forward_loss(batch)
            grad_scaler.scale(loss / accum).backward()

            if fgm is not None and step % fgm_every == 0:
                fgm.attack()
                adv_loss, _ = forward_loss(batch)
                grad_scaler.scale(adv_loss / accum).backward()
                fgm.restore()

            if (step + 1) % accum == 0:
                grad_scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), float(tcfg.get("grad_clip", 1.0)))
                grad_scaler.step(optimizer)
                grad_scaler.update()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)
                if ema:
                    ema.update()
                global_step += 1
                if eval_every and global_step % eval_every == 0:
                    run_eval_and_maybe_save(f"ep{epoch + 1}-step{global_step}")
                    if bad_epochs >= patience:
                        stop = True
                        break

            run_loss += float(loss.item())
            run_correct += int((logits.argmax(-1).cpu() == batch["label"]).sum())
            run_n += len(batch["label"])
            if step % 50 == 0:
                log.info("ep %d step %d/%d loss=%.4f acc=%.3f lr=%.2e elapsed=%.0fs",
                         epoch + 1, step, len(train_loader), run_loss / (step + 1), run_correct / max(run_n, 1),
                         scheduler.get_last_lr()[0], time.time() - t0)
            if dry_run and step >= 2:
                break
        if stop:
            log.info("early stop (patience=%d)", patience)
            break
        run_eval_and_maybe_save(f"ep{epoch + 1}")
        if bad_epochs >= patience:
            log.info("early stop after epoch %d (patience=%d)", epoch + 1, patience)
            break

    # ---- test（可选）
    test_path = dcfg.get("test_jsonl")
    if test_path and os.path.exists(test_path) and os.path.exists(best_state_path) and not dry_run:
        from ml.common.checkpoint import load_detector_from_checkpoint
        best = load_detector_from_checkpoint(best_state_path, device=device)
        test_raw = load_jsonl(test_path, min_chars=min_chars)
        test_ds = TextAIGCDataset(test_raw, best.tokenizer, best.max_length, best.scaler, best.uses_surface, 0.0)
        test_loader = DataLoader(test_ds, batch_size=int(tcfg["batch_size"]) * 2, collate_fn=collate, num_workers=nw)
        ev = evaluate(best.model, test_loader, device, precision, best.uses_surface)
        from ml.training.text.calibration import CalibrationParams, apply_calibration
        probs = apply_calibration(ev["logits"], CalibrationParams(best.temperature, best.platt_a, best.platt_b))
        best_metrics["test"] = summarize(ev, probs, threshold=best.thresholds.get("default_0_5", 0.5))
        log.info("[test] auroc=%.4f f1=%.4f acc=%.4f tpr@fpr1=%.3f",
                 best_metrics["test"]["auroc"], best_metrics["test"]["f1"], best_metrics["test"]["accuracy"],
                 best_metrics["test"]["tpr_at_fpr_1pct"])

    best_metrics["train_time_sec"] = round(time.time() - t0, 1)
    best_metrics["train_samples"] = len(train_samples)
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(best_metrics, f, ensure_ascii=False, indent=2, default=float)
    if mlrun:
        import mlflow
        mlflow.log_artifact(os.path.join(out_dir, "metrics.json"))
        mlflow.end_run()
    log.info("done. best %s=%.4f → %s", metric_key, best_score, best_state_path)
    return best_metrics


def _log_distribution(samples) -> None:
    by_sc, by_aug, by_src = defaultdict(int), defaultdict(int), defaultdict(int)
    pos = 0
    for s in samples:
        by_sc[s.scenario] += 1
        by_aug[s.augment] += 1
        by_src[s.source] += 1
        pos += s.label
    log.info("label: ai=%d human=%d", pos, len(samples) - pos)
    log.info("scenario: %s", dict(sorted(by_sc.items())))
    log.info("augment: %s", dict(sorted(by_aug.items())))
    log.info("source: %s", dict(sorted(by_src.items())))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True, help="ml/configs/text/*.yaml")
    p.add_argument("--max-train-samples", type=int, default=None, help="冒烟用：截断训练集")
    p.add_argument("--epochs", type=int, default=None, help="覆盖 yaml 里的 epochs")
    p.add_argument("--dry-run", action="store_true", help="只跑几个 step 验证链路，不落盘")
    args = p.parse_args()
    cfg = load_config(args.config)
    train(cfg, max_train_samples=args.max_train_samples, epochs_override=args.epochs, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
