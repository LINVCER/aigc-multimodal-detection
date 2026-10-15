"""
定时批量刷新（推荐运行方式，不常驻）
====================================

学校红线几乎不变，不需要常驻服务。由系统计划任务每 2~5 天跑一次本脚本：
读 seeds.csv → 跳过近 N 天已爬的学校 → 逐校礼貌深挖 → 候选去重写出 candidates.{csv,sql,jsonl} →
更新 state.json 记录每校上次爬取时间。候选仍 status=pending，带原文地址，交后台人工审核。

cron（每 3 天凌晨 3 点）::
    0 3 */3 * * cd /app/tools/highschool-spider && python schedule.py --seeds seeds.csv --out out --min-interval-days 3

Windows 计划任务：触发器设每 3 天，操作 `python schedule.py --seeds seeds.csv --out out --min-interval-days 3`。
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
import time
from types import SimpleNamespace

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetcher import Politeness  # noqa: E402
from spider import crawl_seed, load_seeds, write_out  # noqa: E402
from to_sql import rows_to_sql  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")
log = logging.getLogger("hsspider.schedule")

DEFAULTS = dict(delay=2.0, depth=4, max_pages=150, max_attachments=20,
                timeout=20, max_bytes=2_000_000, cache_dir="", dry_run=False, deep=True)


def _load_state(path: str) -> dict:
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return {}


def _save_state(path: str, state: dict) -> None:
    io.open(path, "w", encoding="utf-8").write(json.dumps(state, ensure_ascii=False, indent=2))


def due(seed: dict, state: dict, min_interval_days: float, now: float) -> bool:
    """近 min_interval_days 天内爬过就跳过。"""
    last = state.get(seed.get("school_id") or seed["entry_url"], {}).get("last_crawl", 0)
    return (now - last) >= min_interval_days * 86400


def run(args) -> None:
    seeds = load_seeds(args.seeds)
    state = _load_state(args.state)
    now = time.time()
    todo = [s for s in seeds if due(s, state, args.min_interval_days, now)]
    log.info("种子 %d 所，本次待刷新 %d 所（间隔阈值 %g 天）", len(seeds), len(todo), args.min_interval_days)
    if args.dry_run:
        for s in todo:
            log.info("[dry-run] 将刷新 %s %s", s.get("school_name"), s["entry_url"])
        return

    pol = Politeness(args.delay, requests.Session())
    session = requests.Session()
    sargs = SimpleNamespace(**DEFAULTS)
    all_cand: list[dict] = []
    pages_out: list[dict] = []
    for s in todo:
        try:
            rows = crawl_seed(s, pol, session, sargs, pages_out)
            all_cand.extend(rows)
            key = s.get("school_id") or s["entry_url"]
            state[key] = {"last_crawl": time.time(), "school_name": s.get("school_name", ""),
                          "candidate_count": len(rows)}
        except Exception as e:
            log.exception("%s 刷新出错：%s", s.get("school_name"), e)
    if all_cand:
        write_out(all_cand, args.out)
        io.open(os.path.join(args.out, "candidates.sql"), "w", encoding="utf-8").write(rows_to_sql(all_cand))
        log.info("写出 %s/candidates.sql", args.out)
    _save_state(args.state, state)
    log.info("本次刷新 %d 所，候选 %d 条", len(todo), len(all_cand))


def _selftest() -> None:
    now = time.time()
    st = {"1": {"last_crawl": now - 1 * 86400}, "2": {"last_crawl": now - 10 * 86400}}
    assert not due({"school_id": "1", "entry_url": "x"}, st, 3, now), "1 天前爬过，间隔 3 天应跳过"
    assert due({"school_id": "2", "entry_url": "y"}, st, 3, now), "10 天前爬过，应刷新"
    assert due({"school_id": "9", "entry_url": "z"}, st, 3, now), "没爬过应刷新"
    print("schedule selftest ok：间隔跳过逻辑正确")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="学校红线定时批量刷新（不常驻，交计划任务跑）")
    ap.add_argument("--seeds", help="seeds csv")
    ap.add_argument("--out", default="out")
    ap.add_argument("--state", default="out/state.json", help="记录每校上次爬取时间")
    ap.add_argument("--min-interval-days", type=float, default=3.0, help="同校最小刷新间隔天数（2~5）")
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        _selftest()
    elif a.seeds:
        run(a)
    else:
        ap.error("需要 --seeds 或 --selftest")
