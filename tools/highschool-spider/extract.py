"""
红线候选抽取（通用规则）
========================

从一段已抽好的正文里，找出「学位论文 AIGC 检测 / 查重」相关的阈值候选，产出可人工复核的结构化行。
只负责把证据找出来，不做判定：每条候选都带原文片段 snippet 与来源 URL，最终由后台人工审核落 edu_school_rule。

candidate 字段对齐 docs/design/202610-school-redline-plan.md §2.2。

单测：python tools/highschool-spider/extract.py --selftest
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

DEGREE_KW = {
    "phd": ["博士", "博士生", "博士学位", "博士研究生"],
    "master": ["硕士", "硕士生", "硕士学位", "硕士研究生", "专业学位", "专硕", "学硕"],
    "bachelor": ["本科", "学士", "本科生", "学士学位", "本科毕业论文", "本科毕业设计"],
}
AI_KW = ["aigc", "ai率", "ai 率", "生成式", "智能生成", "人工智能生成", "ai生成",
         "生成内容", "ai检测", "aigc检测", "智能写作", "机器生成"]
PLAG_KW = ["查重", "重复率", "文字复制比", "复制比", "相似度", "去除引用", "总文字复制比", "重合率"]
# 阈值语气词：出现它才认为这个百分比是「红线」，不是统计口径里随便一个数字
LIMIT_CTX = ["不得超过", "不超过", "不得高于", "不高于", "低于", "不低于", "应低于",
             "控制在", "以内", "以下", "≤", "<", "不得大于", "原则上", "要求"]
PLATFORM_KW = {
    "cnki": ["知网", "cnki", "中国知网", "学术不端", "amlc", "tmlc", "科研诚信"],
    "vip": ["维普", "vip"],
    "wanfang": ["万方"],
    "gezida": ["格子达"],
    "paperpass": ["paperpass"],
    "turnitin": ["turnitin"],
}

_PCT = re.compile(r"(\d{1,3}(?:\.\d{1,2})?)\s*(?:%|％|percent|个百分点)")
_YEAR = re.compile(r"(20[12]\d)\s*(?:年|届|级|—|-|学年)")
_CLAUSE_SPLIT = re.compile(r"[。；;！!\n\r]+")


def _norm(text: str) -> str:
    """全角数字 / 百分号 / 空白归一，便于正则命中。"""
    table = {ord("％"): "%", ord("："): ":", ord("，"): ",", ord("（"): "(", ord("）"): ")"}
    text = text.translate(table)
    for i, c in enumerate("０１２３４５６７８９"):
        text = text.replace(c, str(i))
    return text


def _find_kw(s: str, kws: list[str]) -> str | None:
    low = s.lower()
    for k in kws:
        if k in low:
            return k
    return None


def _degree_in(s: str) -> str | None:
    """博士优先于硕士优先于本科，避免「硕士、博士」同句被本科截胡。"""
    low = s.lower()
    for deg in ("phd", "master", "bachelor"):
        if any(k in low for k in DEGREE_KW[deg]):
            return deg
    return None


def _platform_in(s: str) -> str | None:
    low = s.lower()
    for plat, kws in PLATFORM_KW.items():
        if any(k in low for k in kws):
            return plat
    return None


@dataclass
class Candidate:
    school_id: str
    school_name: str
    degree_type: str
    metric: str
    limit_pct: float
    platform: str
    effective_year: int | None
    snippet: str
    source_url: str
    confidence: int
    notice_title: str = ""   # 基本信息：来源通知标题
    publish_date: str = ""   # 基本信息：通知发布日期


_DATE = re.compile(r"(20[12]\d)[-/.年](\d{1,2})[-/.月](\d{1,2})")
_ROUNDS = re.compile(r"(?:检测|送检|查重|检测机会)[^。；\n]{0,8}?(\d)\s*次")
SCOPE_KW = ["全日制", "非全日制", "专业学位", "学术学位", "同等学力", "留学生", "本科", "硕士", "博士", "专硕", "学硕"]
DEPT_KW = ["研究生院", "教务处", "学位办", "学位评定", "质量监督", "学院"]


def extract_basics(text: str, notice_title: str = "") -> dict:
    """抽通知的基本信息，供人工复核时了解背景：发布日期、适用范围、检测工具、送检次数、是否免费、归口部门。"""
    t = _norm(text or "")
    dm = _DATE.search(t)
    publish_date = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}" if dm else ""
    rounds = ""
    rm = _ROUNDS.search(t)
    if rm:
        rounds = rm.group(1)
    low = t.lower()
    return {
        "notice_title": notice_title.strip()[:120],
        "publish_date": publish_date,
        "platform": _platform_in(t) or "",
        "applies_to": [k for k in SCOPE_KW if k in t],
        "detect_rounds": rounds,
        "free": ("免费" in t),
        "department": next((k for k in DEPT_KW if k in notice_title or k in t), ""),
    }


def page_is_relevant(text: str) -> bool:
    """整页是否值得抽取：同时沾 (AIGC 或 查重) + 百分比。爬虫侧先粗筛。"""
    low = _norm(text or "").lower()
    hit_metric = any(k in low for k in AI_KW) or any(k in low for k in PLAG_KW)
    return hit_metric and bool(_PCT.search(low))


def extract_rules(text: str, source_url: str, school_id: str = "", school_name: str = "",
                  notice_title: str = "", publish_date: str = "") -> list[dict]:
    """从正文抽红线候选。按子句顺序扫描，学位标题作为上下文带给后续子句。notice_title/publish_date 作为基本信息随每条候选带出。"""
    text = _norm(text or "")
    page_year = None
    ym = _YEAR.search(text)
    if ym:
        page_year = int(ym.group(1))
    page_platform = _platform_in(text) or ""  # 平台多在「检测工具」段统一声明，作全页兜底

    out: list[dict] = []
    seen: set[tuple] = set()
    current_degree: str | None = None

    for clause in _CLAUSE_SPLIT.split(text):
        clause = clause.strip()
        if not clause:
            continue
        deg_here = _degree_in(clause)
        if deg_here:
            current_degree = deg_here

        if not _PCT.search(clause):
            continue

        # 收集本句里每个指标关键词的位置，用来把每个百分比配给它最近的前一个指标词
        low = clause.lower()
        metric_hits: list[tuple[int, str]] = []
        for k in AI_KW:
            i = low.find(k)
            while i != -1:
                metric_hits.append((i, "ai_rate"))
                i = low.find(k, i + 1)
        for k in PLAG_KW:
            i = low.find(k)
            while i != -1:
                metric_hits.append((i, "plagiarism"))
                i = low.find(k, i + 1)
        if not metric_hits:
            continue  # 有百分比但不沾 AIGC / 查重，跳过
        metric_hits.sort()
        only_kind = {m for _, m in metric_hits}

        has_limit = _find_kw(clause, LIMIT_CTX)
        platform = _platform_in(clause) or page_platform
        yh = _YEAR.search(clause)
        year = int(yh.group(1)) if yh else page_year
        degree = deg_here or current_degree or "unknown"

        for m in _PCT.finditer(clause):
            try:
                val = float(m.group(1))
            except ValueError:
                continue
            if val <= 0 or val > 100:
                continue
            # 百分比归给它前面最近的指标词；句内无前置指标词时，仅当全句只有一种指标才敢认
            preceding = [mt for p, mt in metric_hits if p < m.start()]
            if preceding:
                metric = preceding[-1]
            elif len(only_kind) == 1:
                metric = next(iter(only_kind))
            else:
                continue
            key = (degree, metric, round(val, 2), source_url)
            if key in seen:
                continue
            seen.add(key)
            conf = 40 + (25 if has_limit else 0) + (20 if degree != "unknown" else 0)
            conf += (10 if platform else 0) + (5 if year else 0)
            out.append(asdict(Candidate(
                school_id=school_id, school_name=school_name, degree_type=degree,
                metric=metric, limit_pct=val, platform=platform, effective_year=year,
                snippet=clause[:160], source_url=source_url, confidence=min(conf, 100),
                notice_title=notice_title[:120], publish_date=publish_date,
            )))
    return out


SELFTEST_HTML = """
关于2026届研究生学位论文AIGC检测与学术不端检测的通知

一、检测工具
学校统一使用中国知网学位论文AIGC检测系统及学术不端行为检测系统（AMLC）。

二、检测标准
1. 博士学位论文：AIGC检测结果中AI生成内容占比不得超过15%，去除引用后文字复制比不得超过8%。
2. 硕士学位论文：智能生成内容比例不得超过20%，总文字复制比应低于15%。
3. 本科毕业论文（设计）：AI生成内容原则上控制在25%以内，重复率不得超过20%。

三、其它
论文被引率、分布情况见附件，正常引用不计入复制比。
"""


def _selftest() -> None:
    rows = extract_rules(SELFTEST_HTML, "http://yjsy.example.edu.cn/notice/123.html", "1", "示例大学")
    assert page_is_relevant(SELFTEST_HTML)
    got = {(r["degree_type"], r["metric"]): r["limit_pct"] for r in rows}
    expect = {
        ("phd", "ai_rate"): 15.0, ("phd", "plagiarism"): 8.0,
        ("master", "ai_rate"): 20.0, ("master", "plagiarism"): 15.0,
        ("bachelor", "ai_rate"): 25.0, ("bachelor", "plagiarism"): 20.0,
    }
    for k, v in expect.items():
        assert got.get(k) == v, f"{k} 期望 {v}，实际 {got.get(k)}；全部={got}"
    assert all(r["platform"] == "cnki" for r in rows)
    assert all(r["effective_year"] == 2026 for r in rows)
    assert all(r["confidence"] >= 80 for r in rows)
    print(f"extract selftest ok: {len(rows)} 条候选")
    for r in rows:
        print(f"  {r['degree_type']:8} {r['metric']:10} {r['limit_pct']:>5}%  conf={r['confidence']}  {r['platform']}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--file", help="抽取单个本地已转好的正文 txt")
    args = ap.parse_args()
    if args.selftest:
        _selftest()
    elif args.file:
        import io
        txt = io.open(args.file, encoding="utf-8", errors="replace").read()
        for r in extract_rules(txt, f"file://{args.file}"):
            print(r)
