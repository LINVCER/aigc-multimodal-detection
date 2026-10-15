"""
服务层存储：SQLite 持久化 crawl_job 与候选（常驻服务重启不丢任务）
=================================================================

两条铁律（本轮决策）：
- 一律人工审核：候选只写 status='pending'，服务永不发布 edu_school_rule，发布动作在 Java 后台人工做；
- 必带原文地址：无 source_url 的候选直接拒收。

Java 后台按 GET /candidates 拉 pending 候选，核对 source_url 后入 MySQL edu_school_rule_candidate 审核队列。
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

_DDL = """
CREATE TABLE IF NOT EXISTS crawl_job (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  school_id   TEXT,
  school_name TEXT,
  entry_url   TEXT NOT NULL,
  adapter     TEXT DEFAULT 'generic',
  deep        INTEGER DEFAULT 1,
  status      TEXT NOT NULL DEFAULT 'queued',   -- queued / running / done / failed
  detail      TEXT DEFAULT '',
  candidate_count INTEGER DEFAULT 0,
  created_at  REAL NOT NULL,
  updated_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS candidate (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id      INTEGER NOT NULL,
  school_id   TEXT,
  school_name TEXT,
  degree_type TEXT,
  metric      TEXT,
  limit_pct   REAL,
  platform    TEXT,
  effective_year INTEGER,
  notice_title TEXT,
  publish_date TEXT,
  snippet     TEXT,
  source_url  TEXT NOT NULL,              -- 必带原文地址
  confidence  INTEGER,
  content_hash TEXT UNIQUE,
  status      TEXT NOT NULL DEFAULT 'pending',
  created_at  REAL NOT NULL
);
"""


class Store:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._db.executescript(_DDL)
        self._db.commit()
        # 崩溃残留的 running 任务回到 queued，重启后重跑
        with self._lock:
            self._db.execute("UPDATE crawl_job SET status='queued' WHERE status='running'")
            self._db.commit()

    # ---- job ----
    def enqueue(self, school_id: str, school_name: str, entry_url: str, adapter: str, deep: bool) -> int:
        now = time.time()
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO crawl_job(school_id,school_name,entry_url,adapter,deep,status,created_at,updated_at)"
                " VALUES(?,?,?,?,?, 'queued', ?, ?)",
                (school_id, school_name, entry_url, adapter, 1 if deep else 0, now, now))
            self._db.commit()
            return cur.lastrowid

    def claim_next(self) -> dict | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM crawl_job WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
            if not row:
                return None
            self._db.execute("UPDATE crawl_job SET status='running', updated_at=? WHERE id=?",
                             (time.time(), row["id"]))
            self._db.commit()
            return dict(row)

    def finish(self, job_id: int, status: str, detail: str, candidate_count: int) -> None:
        with self._lock:
            self._db.execute("UPDATE crawl_job SET status=?, detail=?, candidate_count=?, updated_at=? WHERE id=?",
                             (status, detail[:500], candidate_count, time.time(), job_id))
            self._db.commit()

    def job(self, job_id: int) -> dict | None:
        row = self._db.execute("SELECT * FROM crawl_job WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def recent_jobs(self, limit: int = 50) -> list[dict]:
        rows = self._db.execute("SELECT * FROM crawl_job ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ---- candidate ----
    def add_candidates(self, job_id: int, rows: list[dict]) -> int:
        now = time.time()
        n = 0
        with self._lock:
            for r in rows:
                src = (r.get("source_url") or "").strip()
                if not src:
                    continue  # 必带原文地址，否则拒收
                try:
                    self._db.execute(
                        "INSERT OR IGNORE INTO candidate(job_id,school_id,school_name,degree_type,metric,limit_pct,"
                        "platform,effective_year,notice_title,publish_date,snippet,source_url,confidence,content_hash,status,created_at)"
                        " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'pending', ?)",
                        (job_id, r.get("school_id"), r.get("school_name"), r.get("degree_type"), r.get("metric"),
                         r.get("limit_pct"), r.get("platform"), r.get("effective_year"), r.get("notice_title"),
                         r.get("publish_date"), (r.get("snippet") or "")[:255], src, r.get("confidence"),
                         r.get("content_hash") or _hash(r), now))
                    n += self._db.total_changes and 1 or 0
                except sqlite3.IntegrityError:
                    pass
            self._db.commit()
        return n

    def candidates(self, status: str = "pending", limit: int = 500) -> list[dict]:
        rows = self._db.execute("SELECT * FROM candidate WHERE status=? ORDER BY confidence DESC, id DESC LIMIT ?",
                                (status, limit)).fetchall()
        return [dict(r) for r in rows]


def _hash(r: dict) -> str:
    import hashlib
    key = f"{r.get('school_id','')}|{r.get('degree_type','')}|{r.get('metric','')}|{r.get('limit_pct','')}|{r.get('source_url','')}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()
