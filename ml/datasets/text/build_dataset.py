"""
数据集构建：公开集拉取 → 统一 schema → 清洗 / PII / 去重 → 按原文分组划分 train / val / test
==============================================================================================

用法::

    python -m ml.datasets.text.build_dataset --sources hc3,csl,m4 --out ml/datasets/text/data
    python -m ml.datasets.text.build_dataset --sources cheat --cheat-dir ml/datasets/text/raw/cheat
    python -m ml.datasets.text.build_dataset --sources custom --custom-dir ml/datasets/text/raw/custom
    # 训练时要"没见过"某些生成器（cross-generator evals）：
    python -m ml.datasets.text.build_dataset --sources hc3,csl,m4 --held-out-sources qwen,deepseek

数据源与许可（docs/design/DATASETS.md §5）：
    hc3    Hello-SimpleAI/HC3-Chinese   CC-BY-SA   human_answers=0 / chatgpt_answers=1（gpt）
    csl    neuclir/csl                  Apache     中文学术摘要，human=0；scenario=academic_*（按学科粗映射）
    m4     mbzuai-nlp/M4                Apache     多生成器；只取中文
    cheat  手动申请后放 --cheat-dir     研究用     只进 evals，不进 train（默认 --cheat-eval-only）
    custom 自建 JSONL 目录              自建       已是 schema 格式，直接合并

输出::

    {out}/train.jsonl  val.jsonl  test.jsonl        （augment=none，MIN_CHARS≤len≤MAX_CHARS）
    {out}/short.jsonl                                （50 ≤ len < MIN_CHARS，供 short-text evals）
    {out}/held_out.jsonl                             （--held-out-sources 的 AI 样本，供 cross-generator evals）
    {out}/stats.json
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import html
import json
import logging
import os
import random
import re
from collections import Counter, defaultdict

from ml.datasets.text.schema import (
    MAX_CHARS, MIN_CHARS, SCENARIOS, TextSample, content_hash, normalize_source, write_jsonl,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")
log = logging.getLogger("build_dataset")

SHORT_MIN_CHARS = 50

# ---------------------------------------------------------------------------
# 清洗
# ---------------------------------------------------------------------------

_HTML_TAG = re.compile(r"<[^>]{1,200}>")
_URL = re.compile(r"https?://\S+|www\.\S+")
_PHONE = re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_ID_CARD = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_STUDENT_ID = re.compile(r"(?<!\d)(?:20[0-2]\d)\d{6,8}(?!\d)")   # 学号常见 10-12 位且以年份开头
_MULTI_WS = re.compile(r"[ \t　]+")
_MULTI_NL = re.compile(r"\n{2,}")
_SENT_END = "。！？!?"


def clean_text(text: str) -> str:
    t = html.unescape(text or "")
    t = _HTML_TAG.sub(" ", t)
    t = _URL.sub("[URL]", t)
    t = _EMAIL.sub("[EMAIL]", t)
    t = _ID_CARD.sub("[ID]", t)
    t = _PHONE.sub("[PHONE]", t)
    t = _STUDENT_ID.sub("[SID]", t)
    t = t.replace("\r", "\n")
    t = _MULTI_WS.sub(" ", t)
    t = _MULTI_NL.sub("\n", t)
    return t.strip()


def truncate_at_sentence(text: str, max_chars: int = MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    for i in range(len(cut) - 1, max_chars // 2, -1):
        if cut[i] in _SENT_END:
            return cut[: i + 1]
    return cut


def near_dup_key(text: str) -> str:
    """近似去重：去标点后前 160 字的 hash；改写样本不会撞（它们走 augment 流程另有 doc_id）。"""
    core = re.sub(r"[\s，。、！？；：“”‘’（）()\[\]【】《》,.!?;:\"'-]", "", text)[:160]
    return hashlib.md5(core.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 场景映射（公开集只有粗粒度 domain，这里是弱标注；自建数据带真场景）
# ---------------------------------------------------------------------------

HC3_DOMAIN_TO_SCENARIO = {
    "open_qa": "other", "baike": "other", "nlpcc_dbqa": "other",
    "medicine": "academic_bachelor", "finance": "job_report", "psychology": "self_media", "law": "job_report",
}
# CSL 的 discipline 字段是一级学科；理工医 → 硕士，人文社科 → 本科，其余 other
CSL_DISCIPLINE_TO_SCENARIO = {
    "医学": "academic_master", "工学": "academic_master", "理学": "academic_master", "农学": "academic_master",
    "教育学": "academic_bachelor", "文学": "academic_bachelor", "法学": "academic_bachelor",
    "经济学": "academic_bachelor", "管理学": "academic_bachelor", "艺术学": "academic_bachelor",
    "哲学": "academic_phd", "历史学": "academic_phd", "军事学": "academic_phd",
}


def map_scenario(origin: str, raw_domain: str | None) -> str:
    d = (raw_domain or "").strip()
    if origin == "hc3":
        return HC3_DOMAIN_TO_SCENARIO.get(d, "other")
    if origin == "csl":
        for k, v in CSL_DISCIPLINE_TO_SCENARIO.items():
            if k in d:
                return v
        return "academic_master"
    if origin == "cheat":
        return "academic_master"
    if origin == "m4":
        dl = d.lower()
        if "wiki" in dl or "baike" in dl:
            return "other"
        if "news" in dl:
            return "job_report"
        if "abstract" in dl or "arxiv" in dl or "peer" in dl:
            return "academic_master"
        return "self_media"
    return "other"


# ---------------------------------------------------------------------------
# 数据源
# ---------------------------------------------------------------------------

def _hf_load(name: str, *args, **kw):
    from datasets import load_dataset   # 延迟 import：只有真拉数据才需要
    try:
        return load_dataset(name, *args, **kw)
    except Exception as e:
        msg = str(e)
        if any(k in msg for k in ("401", "403", "GatedRepo", "gated", "authenticated")):
            raise SystemExit(
                f"\n{name} 是受限（gated）数据集，未授权访问。三步走：\n"
                f"  1) pip install -U huggingface_hub && hf auth login     # 或 export HF_TOKEN=hf_xxx\n"
                f"  2) 浏览器打开 https://huggingface.co/datasets/{name} 点 Agree 接受条款\n"
                f"  3) 重跑本命令\n"
                f"原始错误：{msg[:200]}\n"
            ) from e
        raise


# CHEAT 各文件 → (label, augment)。官方文件名是 ieee-{init,generation,polish,fusion}
CHEAT_FILE_MAP: dict[str, tuple[int, str]] = {
    "init":       (0, "none"),       # 人写原始摘要
    "generation": (1, "none"),       # ChatGPT 首轮生成
    "polish":     (1, "polished"),   # ChatGPT 润色的人写稿
    "fusion":     (1, "mixcase"),    # 人机句级混合
}

_TEXT_KEYS = ("abstract", "text", "content", "abstract_text", "body", "summary")


def _pick_text(row: dict) -> str:
    for k in _TEXT_KEYS:
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def collect_hc3(max_per_source: int | None) -> list[TextSample]:
    log.info("拉取 HC3-Chinese ...")
    ds = _hf_load("Hello-SimpleAI/HC3-Chinese", "all")["train"]
    out: list[TextSample] = []
    for i, row in enumerate(ds):
        domain = row.get("source", "")
        qid = f"hc3-{domain}-{i:06d}"
        for a in row.get("human_answers") or []:
            out.append(TextSample(text=a, label=0, scenario=map_scenario("hc3", domain), source="human",
                                  origin="hc3", doc_id=qid + "-h", meta={"domain": domain}))
        for a in row.get("chatgpt_answers") or []:
            out.append(TextSample(text=a, label=1, scenario=map_scenario("hc3", domain), source="gpt",
                                  origin="hc3", doc_id=qid + "-a", meta={"domain": domain}))
        if max_per_source and len(out) >= max_per_source:
            break
    return out


def collect_csl(max_per_source: int | None) -> list[TextSample]:
    log.info("拉取 CSL 学术摘要（human 端）...")
    # 全量约 40 万条；不设上限会全读进内存，默认封顶 8 万
    cap = max_per_source or 80_000
    ds = _hf_load("neuclir/csl", split="csl")
    ds = ds.shuffle(seed=42).select(range(min(cap, len(ds))))
    out: list[TextSample] = []
    for i, row in enumerate(ds):
        abstract = row.get("abstract") or row.get("abst") or ""
        disc = row.get("discipline") or row.get("category") or ""
        out.append(TextSample(text=abstract, label=0, scenario=map_scenario("csl", disc), source="human",
                              origin="csl", doc_id=f"csl-{i:07d}", meta={"discipline": disc, "title": row.get("title", "")}))
        if max_per_source and len(out) >= max_per_source:
            break
    return out


M4_LANG_ZH = ("zh", "zh-cn", "zh_cn", "chinese", "中文")


def _m4_label(raw_label, model: str) -> int:
    """M4 的 label 可能是 int / 字符串 / None；认不出来时按生成器名兜底判。"""
    if raw_label is not None:
        s = str(raw_label).strip().lower()
        if s in ("1", "true", "machine", "machine-generated", "ai", "llm"):
            return 1
        if s in ("0", "false", "human", "human-written"):
            return 0
    return 1 if model and model.strip().lower() not in ("human", "") else 0


def collect_m4(max_per_source: int | None) -> list[TextSample]:
    """M4 中文子集。数据集为 gated，需先 `hf auth login` 并在页面接受条款。"""
    log.info("拉取 M4 中文子集（streaming）...")
    ds = _hf_load("mbzuai-nlp/M4", split="train", streaming=True)
    # streaming 默认按分片顺序吐；不 shuffle 会只吃到前几个分片的语料，与生成器分布强相关
    ds = ds.shuffle(buffer_size=10_000, seed=42)
    out: list[TextSample] = []
    logged_keys = False
    scanned = 0
    for row in ds:
        scanned += 1
        if not logged_keys:
            log.info("M4 实际字段：%s", list(row)[:15])
            logged_keys = True
        lang = str(row.get("language") or row.get("lang") or "").strip().lower()
        if lang not in M4_LANG_ZH:
            continue
        text = _pick_text(row)
        if not text:
            continue
        model = str(row.get("model") or row.get("source") or row.get("generator") or "")
        label = _m4_label(row.get("label"), model)
        out.append(TextSample(text=text, label=label,
                              scenario=map_scenario("m4", str(row.get("domain") or "")),
                              source="human" if label == 0 else normalize_source(model), origin="m4",
                              doc_id=f"m4-{scanned:07d}", meta={"model": model}))
        if max_per_source and len(out) >= max_per_source:
            break
    if not out:
        log.warning("M4 一条中文样本都没扫到（扫了 %d 行）——检查上面的实际字段名，language 可能不叫 language", scanned)
    return out


def collect_cheat(cheat_dir: str, max_per_source: int | None) -> list[TextSample]:
    """按官方 release 的四个文件读 CHEAT：ieee-init / ieee-generation / ieee-polish / ieee-fusion。"""
    log.info("读取 CHEAT %s ...", cheat_dir)
    out: list[TextSample] = []
    unknown_schema_logged = False
    for path in sorted(glob.glob(os.path.join(cheat_dir, "**", "*.jsonl"), recursive=True)):
        # 后缀取 ieee-generation → generation；必须精确匹配，不能让 generation 落到默认分支当人类文本
        stem = os.path.splitext(os.path.basename(path))[0].lower().split("-")[-1]
        label, aug = CHEAT_FILE_MAP.get(stem, (1, "none"))
        if stem not in CHEAT_FILE_MAP:
            log.warning("CHEAT 文件名 %s 不在已知集合 %s 内，按 label=1/none 处理", path, sorted(CHEAT_FILE_MAP))
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if not line.strip():
                    continue
                row = json.loads(line)
                text = _pick_text(row)
                if not text and not unknown_schema_logged:
                    log.warning("CHEAT %s 的字段名不在 %s 内，实际键：%s", path, _TEXT_KEYS, list(row)[:12])
                    unknown_schema_logged = True
                rid = row.get("id") or row.get("paper_id") or i
                out.append(TextSample(text=text, label=label, scenario="academic_master",
                                      source="human" if label == 0 else "gpt", augment=aug, origin="cheat",
                                      doc_id=f"cheat-{stem}-{rid}"))
                if max_per_source and len(out) >= max_per_source:
                    return out
    return out


def collect_custom(custom_dir: str) -> list[TextSample]:
    out: list[TextSample] = []
    for path in glob.glob(os.path.join(custom_dir, "**", "*.jsonl"), recursive=True):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    out.append(TextSample.from_dict(json.loads(line)))
    log.info("custom: %d 条 from %s", len(out), custom_dir)
    return out


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def _split_of(doc_id: str, ratios: tuple[float, float, float], seed: int) -> str:
    """按 doc_id 哈希分桶，同一原文（含其改写派生）必然同 split，杜绝泄漏。"""
    h = int(hashlib.md5(f"{seed}:{doc_id}".encode("utf-8")).hexdigest(), 16) % 10_000 / 10_000
    if h < ratios[0]:
        return "train"
    if h < ratios[0] + ratios[1]:
        return "val"
    return "test"


def build(args: argparse.Namespace) -> None:
    random.seed(args.seed)
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    held_out = {normalize_source(s) for s in (args.held_out_sources or "").split(",") if s.strip()}
    os.makedirs(args.out, exist_ok=True)

    raw: list[TextSample] = []
    eval_only: list[TextSample] = []
    for src in sources:
        if src == "hc3":
            raw += collect_hc3(args.max_per_source)
        elif src == "csl":
            raw += collect_csl(args.max_per_source)
        elif src == "m4":
            raw += collect_m4(args.max_per_source)
        elif src == "cheat":
            items = collect_cheat(args.cheat_dir, args.max_per_source)
            (eval_only if args.cheat_eval_only else raw).extend(items)
        elif src == "custom":
            raw += collect_custom(args.custom_dir)
        else:
            raise SystemExit(f"未知数据源 {src}")
    log.info("原始样本 %d（另 eval-only %d）", len(raw), len(eval_only))

    stats: dict = {"input": len(raw), "dropped": Counter(), "by_split": Counter(), "by_scenario": Counter(),
                   "by_source": Counter(), "by_label": Counter(), "held_out_sources": sorted(held_out)}
    seen_exact: set[str] = set()
    seen_near: set[str] = set()
    kept: list[TextSample] = []
    short: list[TextSample] = []
    held: list[TextSample] = []

    for s in raw + eval_only:
        t = clean_text(s.text)
        if len(t) < SHORT_MIN_CHARS:
            stats["dropped"]["too_short"] += 1
            continue
        t = truncate_at_sentence(t)
        h = content_hash(t)
        if h in seen_exact:
            stats["dropped"]["exact_dup"] += 1
            continue
        seen_exact.add(h)
        nk = near_dup_key(t)
        if nk in seen_near:
            stats["dropped"]["near_dup"] += 1
            continue
        seen_near.add(nk)
        s.text = t
        if len(t) < MIN_CHARS:
            s.split = "short"
            short.append(s)
            continue
        if s.label == 1 and s.source in held_out:
            s.split = "held_out"
            held.append(s)
            continue
        if s.origin == "cheat" and args.cheat_eval_only:
            s.split = "test"
        else:
            s.split = _split_of(s.doc_id, (args.train_ratio, args.val_ratio, 1 - args.train_ratio - args.val_ratio), args.seed)
        kept.append(s)

    by_split: dict[str, list[TextSample]] = defaultdict(list)
    for s in kept:
        by_split[s.split].append(s)
        stats["by_split"][s.split] += 1
        stats["by_scenario"][s.scenario] += 1
        stats["by_source"][s.source] += 1
        stats["by_label"][str(s.label)] += 1
    for name in ("train", "val", "test"):
        random.shuffle(by_split[name])
        n = write_jsonl(os.path.join(args.out, f"{name}.jsonl"), by_split[name])
        log.info("%s.jsonl  %d", name, n)
    write_jsonl(os.path.join(args.out, "short.jsonl"), short)
    write_jsonl(os.path.join(args.out, "held_out.jsonl"), held)
    stats["short"] = len(short)
    stats["held_out"] = len(held)
    stats["dropped"] = dict(stats["dropped"])
    for k in ("by_split", "by_scenario", "by_source", "by_label"):
        stats[k] = dict(stats[k])
    with open(os.path.join(args.out, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    log.info("stats: %s", json.dumps(stats, ensure_ascii=False))
    _warn_imbalance(stats)


def _warn_imbalance(stats: dict) -> None:
    by_label = stats.get("by_label", {})
    ai, hu = by_label.get("1", 0), by_label.get("0", 0)
    if ai and hu and (max(ai, hu) / max(min(ai, hu), 1)) > 3:
        log.warning("label 严重不均衡 ai=%d human=%d；训练时 scenario_balanced_sampler 会做每场景内 label 均衡，但建议补齐少数类", ai, hu)
    for sc in SCENARIOS:
        if stats.get("by_scenario", {}).get(sc, 0) < 500:
            log.warning("场景 %s 仅 %d 条，scenario_mix 里的比例将被自动削减；需要自建数据补齐", sc, stats["by_scenario"].get(sc, 0))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sources", default="hc3,csl,m4", help="逗号分隔：hc3,csl,m4,cheat,custom")
    p.add_argument("--out", default="ml/datasets/text/data")
    p.add_argument("--cheat-dir", default="ml/datasets/text/raw/cheat")
    p.add_argument("--cheat-eval-only", action="store_true", default=True, help="CHEAT 研究许可：只进 test（默认开）")
    p.add_argument("--cheat-into-train", dest="cheat_eval_only", action="store_false", help="已取得商业授权时可让 CHEAT 进训练")
    p.add_argument("--custom-dir", default="ml/datasets/text/raw/custom")
    p.add_argument("--held-out-sources", default="", help="这些生成器的 AI 样本不进 train/val/test，单独存 held_out.jsonl（cross-generator evals）")
    p.add_argument("--max-per-source", type=int, default=None)
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--val-ratio", type=float, default=0.1)
    p.add_argument("--seed", type=int, default=42)
    build(p.parse_args())


if __name__ == "__main__":
    main()
