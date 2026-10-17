"""
数据集质控（QC）
================

对齐 dataset-build-plan §3.5：去重 → 长度过滤 → 与种子相似度 → PPL 离群 → 每家族抽检报告。
重依赖（datasketch / sentence-transformers / torch）缺失时自动降级，核心的长度 + 近重复去重始终可跑。

用法::

    python -m ml.datasets.text.qc_dataset --in data/gen/qwen.jsonl data/augment/*.jsonl \
        --out data/clean.jsonl --report data/qc_report.json --dup-threshold 0.8
    python -m ml.datasets.text.qc_dataset --selftest     # 离线合成数据自测
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
from collections import Counter

from ml.common.constants import MAX_CHARS, MIN_CHARS
from ml.datasets.text.schema import TextSample, content_hash, iter_jsonl

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")
log = logging.getLogger("qc_dataset")

_PUNCT = re.compile(r"[\s，。、；：！？,.!?;:]")


def _shingles(text: str, k: int = 5) -> set[str]:
    s = _PUNCT.sub("", text)
    return {s[i:i + k] for i in range(max(0, len(s) - k + 1))} or {s}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter)


class NearDedup:
    """近重复：优先 datasketch MinHashLSH，缺库时退化为字符 5-gram Jaccard（O(n²)，小数据够用）。"""

    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold
        self._lsh = None
        self._mh = {}
        try:
            from datasketch import MinHash, MinHashLSH
            self._MinHash, self._lsh = MinHash, MinHashLSH(threshold=threshold, num_perm=64)
        except Exception:
            log.warning("datasketch 不可用，近重复退化为 O(n²) Jaccard（大数据请装 datasketch）")
            self._seen: list[set[str]] = []

    def is_dup(self, key: str, text: str) -> bool:
        sh = _shingles(text)
        if self._lsh is not None:
            mh = self._MinHash(num_perm=64)
            for s in sh:
                mh.update(s.encode("utf-8"))
            if self._lsh.query(mh):
                return True
            self._lsh.insert(key, mh)
            return False
        for prev in self._seen:
            if _jaccard(sh, prev) >= self.threshold:
                return True
        self._seen.append(sh)
        return False


class SeedSimilarity:
    """与种子相似度：sentence-transformers 可用则算余弦，否则退化为字符 Jaccard。"""

    def __init__(self, lo: float = 0.4, hi: float = 0.85):
        self.lo, self.hi = lo, hi
        self._model = None
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(os.getenv("QC_ST_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"))
        except Exception:
            log.warning("sentence-transformers 不可用，相似度退化为字符 Jaccard")

    def sim(self, text: str, seed: str) -> float:
        if not seed:
            return (self.lo + self.hi) / 2   # 无种子不卡这关
        if self._model is not None:
            import numpy as np
            a, b = self._model.encode([text, seed])
            return float(a @ b / ((np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9))
        return _jaccard(_shingles(text), _shingles(seed))

    def in_range(self, text: str, seed: str) -> bool:
        return self.lo <= self.sim(text, seed) <= self.hi


def run(args) -> None:
    dedup = NearDedup(args.dup_threshold)
    seedsim = SeedSimilarity(args.sim_lo, args.sim_hi) if not args.no_sim else None
    # 种子池：按 seed_doc_id 建索引（若输入里带人类原文）
    seed_text: dict[str, str] = {}
    rows: list[TextSample] = []
    for path in args.inp:
        for s in iter_jsonl(path):
            rows.append(s)
            if s.label == 0:
                seed_text[s.doc_id] = s.text

    drop = Counter()
    kept: list[TextSample] = []
    # 人类（label=0）先过去重，锚定索引：抄了种子的 AI 样本会被判重丢掉，人类原文保留
    for s in sorted(rows, key=lambda x: x.label):
        n = len(s.text)
        if n < MIN_CHARS or n > MAX_CHARS:
            drop["length"] += 1
            continue
        if dedup.is_dup(f"{s.doc_id}:{content_hash(s.text)}", s.text):
            drop["dup"] += 1
            continue
        if seedsim is not None and s.label == 1 and isinstance(s.meta, dict) and s.meta.get("seed_doc_id"):
            seed = seed_text.get(s.meta["seed_doc_id"], "")
            if seed and not seedsim.in_range(s.text, seed):
                drop["similarity"] += 1
                continue
        kept.append(s)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for s in kept:
            f.write(s.to_json() + "\n")

    by_fam = Counter(s.source for s in kept if s.label == 1)
    report = {
        "input": sum(1 for _ in rows), "kept": len(kept), "dropped": dict(drop),
        "by_family_ai": dict(by_fam), "by_label": dict(Counter(s.label for s in kept)),
        "sample_per_family": {fam: [s.text[:60] for s in kept if s.source == fam and s.label == 1][:3]
                              for fam in by_fam},
    }
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    log.info("QC 完成：入 %d / 留 %d，丢弃 %s → %s", len(rows), len(kept), dict(drop), args.out)


def _selftest() -> None:
    import io, tempfile
    d = tempfile.mkdtemp()
    inp = os.path.join(d, "in.jsonl")
    out = os.path.join(d, "clean.jsonl")
    body = "本研究系统分析了数字媒介对城市青年社会资本的影响机制并给出实证结论。" * 4
    samples = [
        TextSample(text=body, label=1, scenario="academic_master", source="qwen", origin="custom",
                   doc_id="a-gen", meta={"seed_doc_id": "a"}),
        TextSample(text=body, label=1, scenario="academic_master", source="qwen", origin="custom",
                   doc_id="a2-gen", meta={"seed_doc_id": "a"}),   # 与上近重复 → 丢
        TextSample(text="太短", label=1, scenario="other", source="gpt", origin="custom", doc_id="b"),  # 长度 → 丢
        TextSample(text="真实人类论文写作风格与机器生成明显不同，句式长短交错，常有具体数据与个人观察的细节描述。" * 3,
                   label=0, scenario="academic_master", source="human", origin="thesis", doc_id="a"),
    ]
    with io.open(inp, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(s.to_json() + "\n")
    args = argparse.Namespace(inp=[inp], out=out, report=None, dup_threshold=0.8,
                              sim_lo=0.4, sim_hi=0.85, no_sim=True)
    run(args)
    kept = [json.loads(l) for l in io.open(out, encoding="utf-8")]
    kept_ids = {r["doc_id"] for r in kept}
    assert "a2-gen" not in kept_ids, "近重复应被去掉"
    assert "b" not in kept_ids, "过短应被去掉"
    assert "a-gen" in kept_ids and "a" in kept_ids, "正常样本与人类原文应保留"
    print(f"qc selftest ok：留 {len(kept)} 条，近重复/过短已剔除")


def main() -> None:
    ap = argparse.ArgumentParser(description="数据集质控（去重/长度/相似度/报告）")
    ap.add_argument("--in", dest="inp", nargs="+", help="输入 JSONL（可多个）")
    ap.add_argument("--out", help="清洗后 JSONL")
    ap.add_argument("--report", help="QC 报告 JSON")
    ap.add_argument("--dup-threshold", type=float, default=0.8)
    ap.add_argument("--sim-lo", type=float, default=0.4)
    ap.add_argument("--sim-hi", type=float, default=0.85)
    ap.add_argument("--no-sim", action="store_true", help="跳过与种子相似度（无 ST 或无种子时）")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        _selftest()
    elif a.inp and a.out:
        run(a)
    else:
        ap.error("需要 --in 和 --out，或 --selftest")


if __name__ == "__main__":
    main()
