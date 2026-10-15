"""
候选 CSV → 归档 SQL（edu_school_rule_candidate 审核队列）
======================================================

把 spider.py 产出的 candidates.csv 转成幂等 INSERT 脚本，交执行方上库（本项目约定：只归档 SQL 不代跑）。
入库即 status=pending，进后台「数据维护」审核队列；content_hash 去重，重复导入不会重复入行。

用法：
    python tools/highschool-spider/to_sql.py --in out/candidates.csv --out out/candidates.sql
    python tools/highschool-spider/to_sql.py --selftest
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io


def _esc(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace("'", "''")


def _hash(r: dict) -> str:
    key = f"{r.get('school_id','')}|{r.get('degree_type','')}|{r.get('metric','')}|{r.get('limit_pct','')}|{r.get('source_url','')}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def rows_to_sql(rows: list[dict]) -> str:
    lines = [
        "-- highschool-spider 候选导入 · 目标表 edu_school_rule_candidate（V0.3.0.014）",
        "-- 幂等：uk_hash 去重，ON DUPLICATE KEY 时只刷新 confidence（取较高）与 snippet；人工审核状态不被覆盖",
        "",
    ]
    seen = set()
    n = 0
    for r in rows:
        h = _hash(r)
        if h in seen:
            continue
        seen.add(h)
        sid = (r.get("school_id") or "").strip()
        sid_sql = sid if sid.isdigit() else "NULL"
        year = (r.get("effective_year") or "").strip()
        year_sql = year if year.isdigit() else "NULL"
        conf = (r.get("confidence") or "0").strip()
        conf_sql = conf if conf.isdigit() else "0"
        lines.append(
            "INSERT INTO edu_school_rule_candidate "
            "(school_id, school_name, degree_type, metric, limit_pct, platform, effective_year, snippet, source_url, confidence, content_hash, status) VALUES ("
            f"{sid_sql}, '{_esc(r.get('school_name',''))}', '{_esc(r.get('degree_type','unknown'))}', "
            f"'{_esc(r.get('metric',''))}', {float(r.get('limit_pct') or 0):.2f}, "
            f"{'NULL' if not r.get('platform') else chr(39) + _esc(r['platform']) + chr(39)}, {year_sql}, "
            f"'{_esc((r.get('snippet') or '')[:255])}', '{_esc(r.get('source_url',''))}', {conf_sql}, '{h}', 'pending')\n"
            "ON DUPLICATE KEY UPDATE confidence = GREATEST(confidence, VALUES(confidence)), snippet = VALUES(snippet);"
        )
        n += 1
    lines.append("")
    lines.append(f"-- 共 {n} 条候选")
    return "\n".join(lines)


def convert(in_csv: str, out_sql: str) -> int:
    with io.open(in_csv, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    sql = rows_to_sql(rows)
    io.open(out_sql, "w", encoding="utf-8").write(sql)
    return sql.count("INSERT INTO")


def _selftest() -> None:
    rows = [
        {"school_id": "1", "school_name": "示例大学", "degree_type": "master", "metric": "ai_rate",
         "limit_pct": "20.0", "platform": "cnki", "effective_year": "2026",
         "snippet": "硕士学位论文：智能生成内容比例不得超过20%", "source_url": "http://x.edu.cn/a.html", "confidence": "100"},
        # 重复行（同 hash）应被去重
        {"school_id": "1", "school_name": "示例大学", "degree_type": "master", "metric": "ai_rate",
         "limit_pct": "20.0", "platform": "cnki", "effective_year": "2026",
         "snippet": "重复", "source_url": "http://x.edu.cn/a.html", "confidence": "90"},
        {"school_id": "", "school_name": "无主候选", "degree_type": "unknown", "metric": "plagiarism",
         "limit_pct": "15", "platform": "", "effective_year": "", "snippet": "o'reilly 带单引号\\反斜杠",
         "source_url": "http://y.edu.cn/b.html", "confidence": "40"},
    ]
    sql = rows_to_sql(rows)
    assert sql.count("INSERT INTO") == 2, "重复候选应去重为 2 条"
    assert "school_id, school_name" in sql
    assert "NULL, '无主候选'" in sql, "无 school_id 应写 NULL"
    assert "''reilly" in sql and "\\\\" in sql, "单引号/反斜杠应转义"
    assert "'pending'" in sql
    assert "ON DUPLICATE KEY UPDATE" in sql
    print("to_sql selftest ok：2 条 INSERT，去重与转义正确")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", help="candidates.csv")
    ap.add_argument("--out", dest="out", default="out/candidates.sql")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        _selftest()
    elif args.inp:
        n = convert(args.inp, args.out)
        print(f"写出 {args.out}，{n} 条 INSERT")
    else:
        ap.error("需要 --in 或 --selftest")
