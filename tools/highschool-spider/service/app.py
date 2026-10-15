"""
highschool-spider 常驻服务（FastAPI，对齐 spider-v2 的 API + worker 形态）
========================================================================

后台（Java）按需投任务：POST /api/v1/crawl；查状态：GET /api/v1/crawl/{id}；
拉候选人工审核：GET /api/v1/candidates?status=pending（每条带 source_url 原文地址）。

启动：
    pip install -r tools/highschool-spider/requirements.txt
    cd tools/highschool-spider
    uvicorn service.app:app --host 0.0.0.0 --port 8200
    # 或独立 worker 进程：python -m service.worker --db out/service.db

lifespan 内起一个后台 worker 线程循环领任务；也可关掉它只跑独立 worker（HSS_INPROC_WORKER=0）。
"""
from __future__ import annotations

import os
import sys
import threading
import time
from contextlib import asynccontextmanager

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fetcher import Politeness  # noqa: E402
from service.store import Store  # noqa: E402
from service.worker import drain_once  # noqa: E402

DB_PATH = os.environ.get("HSS_DB", "out/service.db")
INPROC_WORKER = os.environ.get("HSS_INPROC_WORKER", "1") == "1"

store = Store(DB_PATH)
_pol = Politeness(2.0)
_session = requests.Session()
_stop = threading.Event()


def _worker_loop():
    while not _stop.is_set():
        if not drain_once(store, _pol, _session):
            time.sleep(3.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    t = None
    if INPROC_WORKER:
        t = threading.Thread(target=_worker_loop, daemon=True)
        t.start()
    yield
    _stop.set()


app = FastAPI(title="highschool-spider", version="0.1", lifespan=lifespan)


class CrawlReq(BaseModel):
    entry_url: str
    school_id: str | None = None
    school_name: str | None = None
    adapter: str = "generic"
    deep: bool = True


@app.get("/health")
def health():
    return {"ok": True, "inproc_worker": INPROC_WORKER}


@app.post("/api/v1/crawl")
def submit(req: CrawlReq):
    if not req.entry_url.strip():
        raise HTTPException(400, "entry_url 必填")
    jid = store.enqueue(req.school_id or "", req.school_name or "", req.entry_url.strip(), req.adapter, req.deep)
    return {"jobId": jid, "status": "queued"}


@app.get("/api/v1/crawl/{job_id}")
def job_status(job_id: int):
    j = store.job(job_id)
    if not j:
        raise HTTPException(404, "job 不存在")
    return j


@app.get("/api/v1/crawl")
def jobs(limit: int = 50):
    return {"jobs": store.recent_jobs(limit)}


@app.get("/api/v1/candidates")
def candidates(status: str = "pending", limit: int = 500):
    """供后台拉取人工审核；每条带 source_url 原文地址。服务只产 pending，不发布规则。"""
    return {"candidates": store.candidates(status, limit)}
