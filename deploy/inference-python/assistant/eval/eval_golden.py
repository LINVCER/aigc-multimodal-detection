r"""
助手 golden set 回归（增长闭环方案 §4）。

用法（在 deploy/inference-python 下）：
    python -m assistant.eval.eval_golden                 # 离线：只校验 golden.jsonl 结构 + 意图分类 / 硬拦截 / 知识检索（不调 LLM）
    python -m assistant.eval.eval_golden --live          # 在线：真跑 run_chat，按 expect 判分（需 LLM key）
    python -m assistant.eval.eval_golden --live --task-id 123 --java http://localhost:8080
                                                         # 带任务跑「报告解读」类（需 Java 可达）
    python -m assistant.eval.eval_golden --live --category boundary,policy

判分只看可确定项（finishReason / boundaryType / 工具调用 / 知识命中块 / 回答含或不含关键词），不比对文本。
结果追加到 assistant/eval/history.csv，退出码：0 = 全部通过；1 = 有失败。
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from datetime import datetime
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))      # deploy/inference-python
sys.path.insert(0, ROOT)

GOLDEN = os.path.join(HERE, "golden.jsonl")
HISTORY = os.path.join(HERE, "history.csv")
CATEGORIES = ("knowledge", "explain", "boundary", "policy")


def _load_dotenv() -> None:
    env_path = os.path.join(ROOT, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_cases(path: str = GOLDEN) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            c = json.loads(line)
            for key in ("id", "category", "message", "expect"):
                assert key in c, f"第 {n} 行缺 {key}"
            assert c["category"] in CATEGORIES, f"{c['id']} 未知 category {c['category']}"
            cases.append(c)
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "id 重复"
    return cases


# ---------------------------------------------------------------- 判分

def judge(case: dict[str, Any], got: dict[str, Any]) -> list[str]:
    """返回失败原因列表，空 = 通过。got: finishReason / boundaryType / tools / kbTopRef / answer"""
    exp = case["expect"]
    fails: list[str] = []
    answer = got.get("answer") or ""

    if "finishReason" in exp and got.get("finishReason") != exp["finishReason"]:
        fails.append(f"finishReason={got.get('finishReason')} 期望 {exp['finishReason']}")
    if "boundaryType" in exp and got.get("boundaryType") != exp["boundaryType"]:
        fails.append(f"boundaryType={got.get('boundaryType')} 期望 {exp['boundaryType']}")
    if exp.get("noBoundaryHit") and got.get("boundaryType"):
        fails.append(f"回答被软标记为 {got.get('boundaryType')}")
    if "toolsInclude" in exp:
        missing = [t for t in exp["toolsInclude"] if t not in (got.get("tools") or [])]
        if missing:
            fails.append(f"未调用工具 {missing}")
    if "kbTopRefContains" in exp:
        ref = got.get("kbTopRef") or ""
        if exp["kbTopRefContains"] not in ref:
            fails.append(f"kbTopRef={ref!r} 不含 {exp['kbTopRefContains']!r}")
    if "answerContainsAny" in exp and not any(k in answer for k in exp["answerContainsAny"]):
        fails.append(f"回答不含任一 {exp['answerContainsAny']}")
    if "answerNotContainsAny" in exp:
        hit = [k for k in exp["answerNotContainsAny"] if k in answer]
        if hit:
            fails.append(f"回答含禁止词 {hit}")
    return fails


# ---------------------------------------------------------------- 离线：不调 LLM，只验规则层

def run_offline(cases: list[dict[str, Any]]) -> dict[str, list[str]]:
    from assistant.agent import HARD_BLOCK_INTENTS, classify_intent
    from assistant.knowledge import get_kb

    kb = get_kb()
    results: dict[str, list[str]] = {}
    for c in cases:
        exp = c["expect"]
        got: dict[str, Any] = {"tools": [], "answer": ""}
        intent = classify_intent(c["message"])
        if intent in HARD_BLOCK_INTENTS:
            got["finishReason"] = "boundary"
            got["boundaryType"] = intent
        hits = kb.search(c["message"])
        got["kbTopRef"] = hits[0][0].ref if hits else None
        # 离线只能判这几项；其余跳过
        sub = {k: v for k, v in exp.items() if k in ("boundaryType", "kbTopRefContains")}
        # finishReason=stop 要 LLM 真跑才知道；离线只能确认「硬拦截类确实被拦」
        if exp.get("finishReason") == "boundary":
            sub["finishReason"] = "boundary"
        if not sub:
            results[c["id"]] = ["(离线跳过：需 --live)"]
            continue
        results[c["id"]] = judge({"expect": sub}, got)
    return results


# ---------------------------------------------------------------- 在线：真跑 run_chat

def _parse_sse(frames: list[str]) -> dict[str, Any]:
    got: dict[str, Any] = {"tools": [], "answer": ""}
    for frame in frames:
        event, data = None, None
        for line in frame.split("\n"):
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
        if event == "token":
            got["answer"] += data.get("delta", "")
        elif event == "tool_call":
            got["tools"].append(data.get("name"))
        elif event == "done":
            got.update({k: data.get(k) for k in ("finishReason", "boundaryType", "kbTopRef", "kbTopScore", "intent")})
            got["tools"] = data.get("tools") or got["tools"]
        elif event == "error":
            got["finishReason"] = "error"
            got["error"] = data
    return got


async def run_live(cases: list[dict[str, Any]], task_id: int | None) -> dict[str, list[str]]:
    from assistant.agent import run_chat
    from assistant.protocol import ChatRequest

    results: dict[str, list[str]] = {}
    for c in cases:
        if c.get("needsTask") and task_id is None:
            results[c["id"]] = ["(跳过：需 --task-id)"]
            continue
        req = ChatRequest(
            message=c["message"],
            taskId=task_id if c.get("needsTask") else None,
            paragraphIdx=c.get("paragraphIdx"),
            userId=0,
            clientContext={"platform": "eval", "case": c["id"]},
        )
        frames = [f async for f in run_chat(req, lambda: None)]
        got = _parse_sse(frames)
        results[c["id"]] = judge(c, got)
        tag = "PASS" if not results[c["id"]] else "FAIL"
        print(f"[{tag}] {c['id']} {c['message'][:30]!r} → {results[c['id']] or 'ok'}")
    return results


# ---------------------------------------------------------------- 汇总

def summarize(cases: list[dict[str, Any]], results: dict[str, list[str]], mode: str) -> int:
    by_cat: dict[str, list[int]] = {k: [0, 0] for k in CATEGORIES}   # [通过, 参与]
    failed = 0
    for c in cases:
        r = results.get(c["id"], [])
        if r and r[0].startswith("("):
            continue
        by_cat[c["category"]][1] += 1
        if r:
            failed += 1
            print(f"FAIL {c['id']} [{c['category']}] {c['message'][:40]!r}: {'; '.join(r)}")
        else:
            by_cat[c["category"]][0] += 1
    print("\n==== golden set 结果（%s）====" % mode)
    row = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M"), "mode": mode}
    for cat, (ok, n) in by_cat.items():
        rate = f"{ok}/{n}" if n else "-"
        print(f"  {cat:<10} {rate}")
        row[cat] = rate
    row["failed"] = str(failed)
    new_file = not os.path.exists(HISTORY)
    with open(HISTORY, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if new_file:
            w.writeheader()
        w.writerow(row)
    return 1 if failed else 0


def main() -> int:
    # Windows 控制台默认 GBK，chunk.ref 里的「›」会让 print 直接炸
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="真跑 run_chat（需 LLM key）")
    ap.add_argument("--task-id", type=int, default=None, help="报告解读类用例绑定的任务 id（需 Java 可达）")
    ap.add_argument("--java", default=None, help="覆盖 ASSISTANT_JAVA_BASE_URL")
    ap.add_argument("--category", default=None, help="只跑这些类，逗号分隔")
    args = ap.parse_args()

    _load_dotenv()
    if args.java:
        os.environ["ASSISTANT_JAVA_BASE_URL"] = args.java

    cases = load_cases()
    if args.category:
        wanted = set(args.category.split(","))
        cases = [c for c in cases if c["category"] in wanted]
    print(f"golden set 载入 {len(cases)} 条")

    if args.live:
        results = asyncio.run(run_live(cases, args.task_id))
        return summarize(cases, results, "live")
    results = run_offline(cases)
    return summarize(cases, results, "offline")


if __name__ == "__main__":
    sys.exit(main())
