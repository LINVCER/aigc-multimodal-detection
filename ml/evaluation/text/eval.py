"""
离线评估：对 checkpoint 跑多套评测集，分套报 AUROC / F1 / TPR@FPR / ECE / Brier，并按场景 / 来源 / 增强类型细分
================================================================================================

用法::

    # 自动读 evalset 目录下所有 eval_*.jsonl
    python -m ml.evaluation.text.eval --checkpoint ml/checkpoints/text/v0.2.0-fusion-mdeberta/best.pth \
        --evalset-dir ml/datasets/text/data/evalsets

    # 或显式指定 name=path
    python -m ml.evaluation.text.eval --checkpoint ... --set in_domain=ml/datasets/text/data/test.jsonl

产出：{checkpoint_dir}/eval-report.json + 终端摘要表

验收口径（docs/design/MODEL_UPGRADE_PLAN.md §4 Phase 1）：
    in_domain AUROC ≥ 0.98 · cross_generator F1 ≥ 0.85 · ECE ≤ 0.05 · adversarial F1 ≥ 0.70
"""
from __future__ import annotations

import argparse
import glob
import json
import logging
import os
from collections import defaultdict

import numpy as np
import torch
from torch.utils.data import DataLoader

from ml.common.checkpoint import load_detector_from_checkpoint
from ml.datasets.text.schema import SOURCE_FAMILIES
from ml.training.text.calibration import (
    CalibrationParams, apply_calibration, auroc, binary_metrics, brier, ece, tpr_at_fpr,
)
from ml.training.text.data import TextAIGCDataset, build_collate, load_jsonl

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")
log = logging.getLogger("eval")

# Phase 1 验收线；未达标的项在报告里标 FAIL
ACCEPTANCE = {
    "in_domain": {"auroc": 0.98, "ece_after": 0.05, "source_top1_acc": 0.70},   # 溯源项无溯源头时记 N/A
    "cross_generator": {"f1": 0.85},
    "adversarial": {"f1": 0.70},
    "polished": {"f1": 0.60},
    "mixed": {"f1": 0.60},
    "short_text": {"auroc": 0.85},
}


@torch.no_grad()
def predict(det, samples, device: torch.device, batch_size: int = 32, num_workers: int = 2) -> dict:
    ds = TextAIGCDataset(samples, det.tokenizer, det.max_length, det.scaler, det.uses_surface, augment_prob=0.0)
    loader = DataLoader(ds, batch_size=batch_size, collate_fn=build_collate(det.tokenizer.pad_token_id or 0),
                        num_workers=num_workers)
    logits, labels, src_pred, meta = [], [], [], defaultdict(list)
    det.model.eval()
    for b in loader:
        ids, mask = b["input_ids"].to(device), b["attention_mask"].to(device)
        surf = b["surface"].to(device) if det.uses_surface else None
        out = det.model(ids, mask, surf, return_source=True)
        lg, sl, _ = out if isinstance(out, tuple) else (out, None, None)
        logits.append(lg[:, 1].float().cpu().numpy())
        labels.append(b["label"].numpy())
        if sl is not None:
            src_pred.append(sl.argmax(-1).cpu().numpy())
        meta["scenario"].extend(b["scenario"])
        meta["augment"].extend(b["augment"])
        meta["source_id"].extend(b["source_id"].numpy().tolist())
    return {
        "logits": np.concatenate(logits), "labels": np.concatenate(labels),
        "source_pred": np.concatenate(src_pred) if src_pred else None, **{k: v for k, v in meta.items()},
    }


def score_set(name: str, pred: dict, det, threshold: float) -> dict:
    lg, y = pred["logits"], pred["labels"]
    probs = apply_calibration(lg, CalibrationParams(det.temperature, det.platt_a, det.platt_b))
    raw = 1.0 / (1.0 + np.exp(-lg))
    m = binary_metrics(probs, y, threshold)
    m.update({
        "n": int(len(y)), "n_ai": int(y.sum()), "n_human": int(len(y) - y.sum()),
        "auroc": auroc(lg, y), "ece_before": ece(raw, y), "ece_after": ece(probs, y), "brier": brier(probs, y),
        "threshold": threshold,
    })
    for t in (0.01, 0.05):
        tpr, thr = tpr_at_fpr(probs, y, t)
        m[f"tpr_at_fpr_{int(t * 100)}pct"] = tpr
    # 分组
    for gname in ("scenario", "augment"):
        groups = defaultdict(list)
        for i, k in enumerate(pred[gname]):
            groups[k].append(i)
        m[f"by_{gname}"] = {}
        for k, idx in sorted(groups.items()):
            idx = np.asarray(idx)
            gm = binary_metrics(probs[idx], y[idx], threshold)
            gm["n"] = int(len(idx))
            if y[idx].min() != y[idx].max():
                gm["auroc"] = auroc(lg[idx], y[idx])
            m[f"by_{gname}"][k] = gm
    # 按来源家族看召回（AI 样本）与假阳（human）
    groups = defaultdict(list)
    for i, sid in enumerate(pred["source_id"]):
        groups[SOURCE_FAMILIES[sid] if sid < len(SOURCE_FAMILIES) else "other"].append(i)
    m["by_source"] = {}
    for k, idx in sorted(groups.items()):
        idx = np.asarray(idx)
        gm = binary_metrics(probs[idx], y[idx], threshold)
        gm["n"] = int(len(idx))
        m["by_source"][k] = gm
    # 溯源头 top-1（若有）
    if pred.get("source_pred") is not None:
        sid = np.asarray(pred["source_id"])
        m["source_top1_acc"] = float((pred["source_pred"] == sid).mean())
    # 验收
    acc = ACCEPTANCE.get(name, {})
    m["acceptance"] = {}
    for k, line in acc.items():
        v = m.get(k)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            # 指标不可用（如 cls_only 无溯源头）→ N/A，不算 FAIL
            m["acceptance"][k] = {"target": line, "value": None, "pass": None}
            continue
        ok = (v <= line) if k.startswith("ece") else (v >= line)
        m["acceptance"][k] = {"target": line, "value": v, "pass": bool(ok)}
    return m


def _pass_label(v: dict) -> str:
    return "N/A" if v["pass"] is None else ("PASS" if v["pass"] else "FAIL")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--evalset-dir", help="目录下所有 eval_*.jsonl")
    p.add_argument("--set", action="append", default=[], help="name=path，可重复")
    p.add_argument("--base-model", default=None, help="legacy checkpoint 需指定 backbone 路径")
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--threshold-key", default="default_0_5", help="checkpoint.thresholds 里的键：default_0_5 / fpr_1pct / fpr_5pct / youden")
    p.add_argument("--out", default=None, help="报告路径，默认 checkpoint 同目录 eval-report.json")
    args = p.parse_args()

    sets: dict[str, str] = {}
    if args.evalset_dir:
        for f in sorted(glob.glob(os.path.join(args.evalset_dir, "eval_*.jsonl"))):
            sets[os.path.basename(f)[len("eval_"):-len(".jsonl")]] = f
    for item in args.set:
        name, path = item.split("=", 1)
        sets[name] = path
    if not sets:
        raise SystemExit("没有评测集：给 --evalset-dir 或 --set name=path")

    device = torch.device(args.device)
    det = load_detector_from_checkpoint(args.checkpoint, device=device, base_model_override=args.base_model)
    threshold = float(det.thresholds.get(args.threshold_key, 0.5))
    log.info("checkpoint=%s arch=%s legacy=%s T=%.3f a=%.3f b=%.3f threshold[%s]=%.3f",
             args.checkpoint, det.arch, det.is_legacy, det.temperature, det.platt_a, det.platt_b,
             args.threshold_key, threshold)

    report = {"checkpoint": args.checkpoint, "version": det.hparams.get("version"), "arch": det.arch,
              "threshold_key": args.threshold_key, "threshold": threshold, "sets": {}}
    for name, path in sets.items():
        samples = load_jsonl(path, min_chars=0)
        if not samples:
            log.warning("%s 为空，跳过", path)
            continue
        pred = predict(det, samples, device, args.batch_size)
        report["sets"][name] = score_set(name, pred, det, threshold)
        m = report["sets"][name]
        log.info("%-16s n=%-6d auroc=%.4f f1=%.4f acc=%.4f fpr=%.3f tpr@fpr1=%.3f ece=%.4f brier=%.4f %s",
                 name, m["n"], m["auroc"], m["f1"], m["accuracy"], m["fpr"], m["tpr_at_fpr_1pct"],
                 m["ece_after"], m["brier"],
                 " ".join(f"{k}:{_pass_label(v)}" for k, v in m["acceptance"].items()))

    out = args.out or os.path.join(os.path.dirname(args.checkpoint) or ".", "eval-report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=float)
    log.info("report -> %s", out)


if __name__ == "__main__":
    main()
