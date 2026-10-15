"""
爬取 worker：领 queued 任务 → 跑 highschool-spider → 候选落库（status=pending）
=============================================================================

常驻服务里由 app 的 lifespan 起一个后台线程循环调 drain_once；也可单独进程跑 run_forever。
全局限速用一个共享 Politeness，避免多任务对同域猛拉。
"""
from __future__ import annotations

import logging
import os
import sys
import time
from types import SimpleNamespace

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import extract  # noqa: E402
from fetcher import Politeness  # noqa: E402
from service.store import Store  # noqa: E402
from spider import crawl_seed  # noqa: E402

log = logging.getLogger("hsspider.worker")

# 服务默认参数：礼貌但深挖
DEFAULTS = dict(delay=2.0, depth=4, max_pages=150, max_attachments=20,
                timeout=20, max_bytes=2_000_000, cache_dir="", dry_run=False)


def _run_job(job: dict, pol: Politeness, session: requests.Session) -> tuple[str, str, list[dict]]:
    seed = {"school_id": str(job.get("school_id") or ""), "school_name": job.get("school_name") or "",
            "entry_url": job["entry_url"]}
    args = SimpleNamespace(**{**DEFAULTS, "deep": bool(job.get("deep", 1))})

    # selftest: 入口以 selftest: 开头时用内置样例跑抽取，供离线/冒烟测试，不联网
    if job["entry_url"].startswith("selftest:"):
        basics = extract.extract_basics(extract.SELFTEST_HTML, "自测通知")
        rows = extract.extract_rules(extract.SELFTEST_HTML, "http://selftest.example.edu.cn/notice.html",
                                     seed["school_id"], seed["school_name"], basics["notice_title"], basics["publish_date"])
        return "done", f"selftest 抓 1 页，候选 {len(rows)} 条", rows

    pages_out: list[dict] = []
    rows = crawl_seed(seed, pol, session, args, pages_out)
    return "done", f"抓取完成，候选 {len(rows)} 条，命中页 {len(pages_out)}", rows


def drain_once(store: Store, pol: Politeness, session: requests.Session) -> bool:
    """领一个任务跑完；无任务返回 False。"""
    job = store.claim_next()
    if not job:
        return False
    try:
        status, detail, rows = _run_job(job, pol, session)
        n = store.add_candidates(job["id"], rows)
        store.finish(job["id"], status, detail, n)
        log.info("job %s %s：%s（入库 %d）", job["id"], status, detail, n)
    except Exception as e:
        log.exception("job %s 失败：%s", job["id"], e)
        store.finish(job["id"], "failed", str(e), 0)
    return True


def run_forever(db_path: str, idle_sleep: float = 3.0) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")
    store = Store(db_path)
    pol = Politeness(DEFAULTS["delay"])
    session = requests.Session()
    log.info("highschool-spider worker 启动，库 %s", db_path)
    while True:
        if not drain_once(store, pol, session):
            time.sleep(idle_sleep)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="out/service.db")
    run_forever(ap.parse_args().db)
