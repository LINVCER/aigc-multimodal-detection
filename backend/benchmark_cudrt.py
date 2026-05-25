"""
CUDRT 基准测试 — 中文 AIGC 检测器评估

在 CUDRT Chinese 验证集上评估 ImageNious 检测器性能
指标: 准确率 / 精确率 / 召回率 / F1 / ECE
"""

import os, sys, json, time, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def main():
    from app.detectors.text.statistical_features import ChineseStatisticalExtractor
    from app.services.text_service import _statistical_to_output

    # 加载 CUDRT 验证集
    val_path = "../data/CUDRT/Detector/Roberta/Chinese/dataset/val.json"
    with open(val_path, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    print(f"CUDRT 验证集: {len(val_data)} 样本")

    # 采样测试 (取 500 样本加速)
    ai_samples = [s for s in val_data if s["label"] == 1][:250]
    human_samples = [s for s in val_data if s["label"] == 0][:250]
    test_samples = ai_samples + human_samples
    random.shuffle(test_samples)

    print(f"测试集: {len(test_samples)} 样本 (250 AI + 250 Human)")

    extractor = ChineseStatisticalExtractor()
    correct = 0
    tp = fp = tn = fn = 0
    confidences = []

    start = time.time()
    for s in test_samples:
        text = s.get("AI_text") or s.get("human_text") or ""
        if len(text) < 20:
            continue

        feats = extractor.extract(text)
        stat_out = _statistical_to_output(feats)
        predicted = stat_out.confidence > 0.5
        actual = bool(s["label"])

        if predicted:
            if actual: tp += 1
            else: fp += 1
        else:
            if actual: fn += 1
            else: tn += 1

        confidences.append(stat_out.confidence)

    elapsed = time.time() - start

    # 计算指标
    total = tp + fp + tn + fn
    acc = (tp + tn) / total if total > 0 else 0
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0

    # ECE
    conf_mean = sum(confidences) / len(confidences) if confidences else 0
    actual_positive = sum(s["label"] for s in test_samples) / len(test_samples)
    ece = abs(conf_mean - actual_positive)

    print(f"\n{'='*50}")
    print(f"CUDRT 中文基准测试结果")
    print(f"{'='*50}")
    print(f"  样本数:    {total}")
    print(f"  准确率:    {acc:.1%}")
    print(f"  精确率:    {prec:.1%}")
    print(f"  召回率:    {rec:.1%}")
    print(f"  F1 Score:  {f1:.2f}")
    print(f"  ECE:       {ece:.4f}")
    print(f"  推理速度:  {total/elapsed:.0f} 样本/秒")
    print(f"{'='*50}")

    # 保存
    result = {
        "benchmark": "CUDRT Chinese",
        "samples": total,
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "ece": round(ece, 4),
    }
    Path("../data/benchmarks").mkdir(parents=True, exist_ok=True)
    path = f"../data/benchmarks/cudrt_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"结果已保存: {path}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
