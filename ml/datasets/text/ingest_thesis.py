"""
真实论文 → 人类负样本 / 假阳评测集（eval_real_thesis）
=====================================================

把一批真实学位论文（PDF / DOCX / TXT）解析成段落，按 Java TextProcessor 同一套规则切段、排除非正文，
落成 schema 口径的 JSONL。默认产出 label=0 的评测集，用来回答「规范学术写作被判 AI 的比例是多少」。

用法::

    # 评测集（默认）：所有论文 label=0，split=eval_real_thesis
    python -m ml.datasets.text.ingest_thesis --in raw/thesis --out data/evalsets/eval_real_thesis.jsonl --scenario academic_master

    # 带清单：每篇可指定 scenario / year / 需打码的人名，列名 file,scenario,year,names
    python -m ml.datasets.text.ingest_thesis --in raw/thesis --manifest raw/thesis/manifest.csv --out ...

    # 作训练用人类样本（split 留空，交给 build_dataset --sources custom 划分）
    python -m ml.datasets.text.ingest_thesis --in raw/thesis --out raw/custom/thesis_human.jsonl --as-train

红线：
- 论文年份须在 2022 年及以前（ChatGPT 之前），--max-year 之后的文件会被跳过并计数
- PII：复用 build_dataset.clean_text（手机 / 邮箱 / 身份证 / 学号），再打码清单里给的人名；封面 / 声明 / 授权书 / 目录整段丢弃
- 数据不入 git；本脚本只在本地跑
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import statistics
from collections import Counter

from ml.datasets.text.build_dataset import clean_text
from ml.datasets.text.schema import MAX_CHARS, MIN_CHARS, SCENARIOS, TextSample, content_hash, write_jsonl

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")
log = logging.getLogger("ingest_thesis")

# ---------------------------------------------------------------------------
# 与 backend TextProcessor 同一套正则（Java → Python 移植，改一处要两边同步）
# 差异：「第三章 方法」这类「章号 + 标题」同一行的写法 Java 版匹配不到，这里放宽允许章号后带 ≤30 字标题
# ---------------------------------------------------------------------------
REF_START = re.compile(r"^\s*(参考\s*文献|references?|bibliography|致\s*谢|acknowledge?ments?|附\s*录|appendix)\s*$", re.I)
SECTION_TITLE = re.compile(
    r"^\s*(第[一二三四五六七八九十百千0-9]+[章节篇]\s*\S{0,30}|chapter\s+\d+\s*\S{0,30}|\d+(\.\d+)*\s+\S{1,20}|摘\s*要|abstract|引\s*言|introduction"
    r"|结\s*论|conclusion|讨\s*论|discussion|方\s*法|methods?|背\s*景|background|相关工作|related\s+work|实\s*验|experiments?|结\s*果|results?)\s*$",
    re.I)
CAPTION = re.compile(r"^\s*(图|表|figure|table|fig\.|tab\.|公式|equation|eq\.)\s*\d", re.I)
REF_ITEM = re.compile(r"^\s*(\[\d+\]|\(\d+\))\s+\S")

# 学位论文特有的前置页：封面字段、声明、授权书、目录、关键词行。整段丢弃，不进任何集
FRONT_MATTER = re.compile(
    r"(原创性声明|独创性声明|版权使用授权书|使用授权书|使用授权说明|学位论文作者签名|导师签名|签\s*名[:：]|日\s*期[:：]"
    r"|中图分类号|UDC|密\s*级|学校代码|学\s*号[:：]|指导教师[:：]|申请学位|培养单位|答辩委员会|论文提交日期|论文答辩日期"
    r"|^\s*目\s*录\s*$|^\s*contents\s*$|^\s*关键词[:：]|^\s*key\s*words?[:：])",
    re.I | re.M)
TOC_LINE = re.compile(r"[.…·]{4,}\s*\d+\s*$|^\s*\d+(\.\d+)*\s+\S.{0,40}?\s+\d{1,3}\s*$")
PAGE_NO = re.compile(r"^\s*[-—–]?\s*(第\s*)?[0-9ivxlcIVXLC]{1,4}\s*(页)?\s*[-—–]?\s*$")

SECTION_NORMALIZE = [
    (re.compile(r"摘\s*要|abstract", re.I), "摘要"),
    (re.compile(r"引\s*言|绪\s*论|introduction|背\s*景|background", re.I), "引言"),
    (re.compile(r"相关工作|文献综述|related\s+work|literature", re.I), "相关工作"),
    (re.compile(r"方\s*法|设\s*计|模型|方案|methods?|approach", re.I), "方法"),
    (re.compile(r"实\s*验|实\s*现|experiments?|implementation", re.I), "实验"),
    (re.compile(r"结\s*果|分\s*析|results?|analysis", re.I), "结果"),
    (re.compile(r"讨\s*论|discussion", re.I), "讨论"),
    (re.compile(r"结\s*论|总\s*结|展\s*望|conclusion", re.I), "结论"),
]
SENT_END = "。！？!?."


def normalize_section(title: str) -> str:
    for pat, name in SECTION_NORMALIZE:
        if pat.search(title):
            return name
    return "正文"


# ---------------------------------------------------------------------------
# 文件 → 原始文本
# ---------------------------------------------------------------------------

def extract_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".txt":
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    if ext == ".docx":
        try:
            import docx  # python-docx
        except ImportError as e:
            raise SystemExit("解析 DOCX 需要 python-docx：pip install python-docx") from e
        d = docx.Document(path)
        # DOCX 自带段落边界，用空行隔开让后面的切段直接按空行走
        return "\n\n".join(p.text for p in d.paragraphs)
    if ext == ".pdf":
        try:
            import fitz  # PyMuPDF，版式还原更好
            doc = fitz.open(path)
            return "\n".join(page.get_text("text") for page in doc)
        except ImportError:
            pass
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise SystemExit("解析 PDF 需要 pymupdf 或 pypdf：pip install pymupdf") from e
        reader = PdfReader(path)
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    raise ValueError(f"不支持的文件类型：{path}")


# ---------------------------------------------------------------------------
# 行 → 段落（PDF 抽出的是物理行，先按版式线索回流成逻辑段）
# ---------------------------------------------------------------------------

def reflow_lines(text: str) -> str:
    """
    PDF 行回流：句末标点收尾且下一行以缩进 / 标题开头 → 断段；短行（< 0.6 倍中位行宽）收尾 → 断段；
    页码行、目录行直接丢。DOCX / TXT 已有空行分段的，这一步只去页码。
    """
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    lines = [ln for ln in lines if not PAGE_NO.match(ln) and not TOC_LINE.search(ln)]
    widths = [len(ln) for ln in lines if ln.strip()]
    median = statistics.median(widths) if widths else 40
    out: list[str] = []
    buf = ""
    for ln in lines:
        s = ln.strip()
        if not s:
            if buf:
                out.append(buf)
                buf = ""
            continue
        indented = ln.startswith(("　", "  ", "\t"))
        is_title = SECTION_TITLE.match(s) is not None and len(s) < 40
        if buf and (indented or is_title):
            out.append(buf)
            buf = ""
        buf = (buf + s) if buf else s
        short = len(s) < 0.6 * median
        if (short and s[-1:] in SENT_END) or is_title:
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return "\n\n".join(out)


def classify(text: str, state: dict) -> tuple[str | None, str]:
    """单段分类：返回 (排除原因或 None, 当前章节)。state 跨段携带「已进入参考文献 / 致谢 / 附录」与当前章节。"""
    if state.get("after_reason"):
        return state["after_reason"], state["section"]
    if REF_START.match(text):
        low = text.lower()
        if "致谢" in text or "acknowledge" in low:
            state["after_reason"] = "acknowledgement"
        elif "附录" in text or "appendix" in low:
            state["after_reason"] = "appendix"
        else:
            state["after_reason"] = "reference"
        return state["after_reason"], state["section"]
    if FRONT_MATTER.search(text):
        return "front_matter", state["section"]
    if SECTION_TITLE.match(text) and len(text) < 30:
        state["section"] = normalize_section(text)
        return "sectionTitle", state["section"]
    if CAPTION.search(text):
        return "caption", state["section"]
    if REF_ITEM.search(text) and len(text) < 300:
        return "reference", state["section"]
    return None, state["section"]


def segment_paragraphs(text: str) -> list[dict]:
    """
    空行分段 → 逐段分类 → 只把「正文短片段（<30 字）」并入其后的正文段 → >800 字按句切到 ≥400。
    与 Java TextProcessor 的差别：Java 先无差别合并短段再分类，会把单独成行的「参考文献」「第三章 方法」
    这类标题并进正文导致漏判；这里先分类再合并，标题与参考文献起始行不会被吞掉。
    """
    pieces = [re.sub(r"[\t ]+", " ", raw).strip() for raw in re.split(r"\n\s*\n", text)]
    pieces = [p for p in pieces if p]
    state = {"after_reason": None, "section": "正文"}
    out: list[dict] = []
    pending = ""   # 待并入下一正文段的短片段
    for p in pieces:
        reason, section = classify(p, state)
        if reason is not None:
            if pending:
                out.append({"text": pending, "excluded": False, "reason": None, "section": section})
                pending = ""
            out.append({"text": p, "excluded": True, "reason": reason, "section": section})
            continue
        if len(p) < 30:
            pending = (pending + " " + p) if pending else p
            if len(pending) >= 30:
                out.append({"text": pending, "excluded": False, "reason": None, "section": section})
                pending = ""
            continue
        body = (pending + " " + p) if pending else p
        pending = ""
        if len(body) <= 800:
            out.append({"text": body, "excluded": False, "reason": None, "section": section})
            continue
        chunk = ""
        for ch in body:
            chunk += ch
            if ch in "。！？.!?" and len(chunk) >= 400:
                out.append({"text": chunk.strip(), "excluded": False, "reason": None, "section": section})
                chunk = ""
        if chunk.strip():
            out.append({"text": chunk.strip(), "excluded": False, "reason": None, "section": section})
    if pending:
        out.append({"text": pending, "excluded": False, "reason": None, "section": state["section"]})
    return out


# ---------------------------------------------------------------------------
# 清单与打码
# ---------------------------------------------------------------------------

def load_manifest(path: str | None) -> dict[str, dict]:
    if not path:
        return {}
    rows: dict[str, dict] = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            key = os.path.basename((r.get("file") or "").strip())
            if key:
                rows[key] = r
    return rows


def mask_names(text: str, names: list[str]) -> str:
    for n in sorted({x.strip() for x in names if x and len(x.strip()) >= 2}, key=len, reverse=True):
        text = text.replace(n, "[NAME]")
    return text


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def ingest_file(path: str, meta_row: dict, args: argparse.Namespace, seen: set[str]) -> tuple[list[TextSample], dict]:
    scenario = (meta_row.get("scenario") or args.scenario).strip()
    if scenario not in SCENARIOS:
        raise SystemExit(f"{path}: scenario {scenario!r} 不在 {SCENARIOS}")
    names = [x for x in re.split(r"[,，;；/ ]+", meta_row.get("names") or "") if x]
    year = meta_row.get("year")
    fname = os.path.basename(path)
    stat = {"file": fname, "year": year, "scenario": scenario, "paragraphs": 0, "body": 0, "kept": 0,
            "excluded": Counter(), "short": 0, "dup": 0, "by_section": Counter()}

    raw = extract_text(path)
    if path.lower().endswith(".pdf"):
        raw = reflow_lines(raw)
    elif raw.count(chr(10) * 2) < 3:
        # Word 导出的 TXT 常是一行一段、没有空行：按行分段，否则整篇会被当成一段
        raw = (chr(10) * 2).join(raw.splitlines())
    segs = segment_paragraphs(raw)
    stat["paragraphs"] = len(segs)
    doc_id = f"thesis-{content_hash(fname)[:12]}"
    samples: list[TextSample] = []
    for i, m in enumerate(segs):
        if m["excluded"]:
            stat["excluded"][m["reason"]] += 1
            continue
        stat["body"] += 1
        text = mask_names(clean_text(m["text"]), names)
        if len(text) < MIN_CHARS:
            stat["short"] += 1
            continue
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS]
        h = content_hash(text)
        if h in seen:
            stat["dup"] += 1
            continue
        seen.add(h)
        samples.append(TextSample(
            text=text, label=0, scenario=scenario, source="human", augment="none", origin="thesis",
            doc_id=doc_id, split="" if args.as_train else "eval_real_thesis",
            meta={"file": fname, "section": m["section"], "para_idx": i, "year": year or None},
        ))
        stat["by_section"][m["section"]] += 1
    stat["kept"] = len(samples)
    return samples, stat


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--in", dest="inp", required=True, help="论文目录（递归扫 pdf / docx / txt）")
    p.add_argument("--out", required=True, help="输出 jsonl")
    p.add_argument("--manifest", default=None, help="CSV：file,scenario,year,names；缺省全部用 --scenario")
    p.add_argument("--scenario", default="academic_master", help="清单未指定时的默认场景")
    p.add_argument("--max-year", type=int, default=2022, help="超过该年份的论文跳过（ChatGPT 之后不能当纯人类样本）")
    p.add_argument("--as-train", action="store_true", help="split 留空作训练用人类样本，而不是评测集")
    p.add_argument("--max-paras-per-doc", type=int, default=0, help="每篇最多保留段数，0 不限（防长论文淹没统计）")
    args = p.parse_args()

    manifest = load_manifest(args.manifest)
    files = sorted(
        os.path.join(r, f) for r, _, fs in os.walk(args.inp) for f in fs
        if f.lower().endswith((".pdf", ".docx", ".txt")) and not f.startswith(("~$", "."))
    )
    if not files:
        raise SystemExit(f"{args.inp} 下没有 pdf / docx / txt")

    seen: set[str] = set()
    all_samples: list[TextSample] = []
    stats: list[dict] = []
    skipped_year = 0
    for path in files:
        row = manifest.get(os.path.basename(path), {})
        y = row.get("year")
        if y and y.strip().isdigit() and int(y) > args.max_year:
            skipped_year += 1
            log.warning("跳过 %s：年份 %s 晚于 %d", os.path.basename(path), y, args.max_year)
            continue
        try:
            samples, st = ingest_file(path, row, args, seen)
        except Exception as e:
            log.error("解析失败 %s: %s", path, e)
            continue
        if args.max_paras_per_doc and len(samples) > args.max_paras_per_doc:
            samples = samples[: args.max_paras_per_doc]
            st["kept"] = len(samples)
        all_samples.extend(samples)
        st["excluded"] = dict(st["excluded"])
        st["by_section"] = dict(st["by_section"])
        stats.append(st)
        log.info("%-40s 段 %4d · 正文 %4d · 入集 %4d · 排除 %s", st["file"][:40], st["paragraphs"], st["body"], st["kept"], st["excluded"])

    if not all_samples:
        raise SystemExit("一条样本都没产出，检查解析与排除规则")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    n = write_jsonl(args.out, all_samples)
    summary = {
        "files": len(stats), "skipped_year": skipped_year, "samples": n,
        "by_section": dict(sum((Counter(s["by_section"]) for s in stats), Counter())),
        "by_scenario": dict(Counter(s.scenario for s in all_samples)),
        "docs_without_manifest_year": sum(1 for s in stats if not s["year"]),
        "per_file": stats,
    }
    with open(os.path.splitext(args.out)[0] + ".stats.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    log.info("写入 %s：%d 篇 → %d 段；分章节 %s", args.out, len(stats), n, summary["by_section"])
    if summary["docs_without_manifest_year"]:
        log.warning("%d 篇没有年份信息，无法确认是否 ChatGPT 之前；请补 manifest 的 year 列", summary["docs_without_manifest_year"])
    if n < 1000:
        log.warning("只有 %d 段，FPR 估计的置信区间会很宽；建议 ≥ 300 篇 / 2 万段", n)


if __name__ == "__main__":
    main()
