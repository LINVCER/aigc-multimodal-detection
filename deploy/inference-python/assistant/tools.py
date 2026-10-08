"""
工具：schema（给模型看）+ 执行器（真干活）。

7 个工具围绕检测场景；唯一写操作 create_appeal 需用户在对话里明确确认。
取业务数据走 Java（鉴权与数据归属在那边），即时检测与表层特征直接用本进程的模型，不绕一圈。
"""
from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

import httpx

from .config import CONFIG
from .knowledge import get_kb

log = logging.getLogger("assistant.tools")

# 与 detectors/text.py 同一套路径探测：ml/common 在仓库根或容器 /app 下
_HERE = os.path.dirname(os.path.abspath(__file__))
for _cand in (os.path.abspath(os.path.join(_HERE, "..")), os.path.abspath(os.path.join(_HERE, "..", "..", ".."))):
    if os.path.isdir(os.path.join(_cand, "ml", "common")) and _cand not in sys.path:
        sys.path.insert(0, _cand)
try:
    from ml.common.surface_features import (  # noqa: E402
        SURFACE_FEATURE_NAMES, document_baseline_zscores, extract_surface_features, load_surface_baseline, surface_facts,
    )
    _SURFACE_OK = True
except Exception as _e:  # numpy / ml 包缺失时只丢证据，不丢对话
    log.warning("surface_features 不可用，助手将无法给表层证据：%s", _e)
    _SURFACE_OK = False

# 由 main.py 注入：返回当前已加载的 TextAIGCDetector（可能为 None → 走 stub 口径说明）
DetectorGetter = Callable[[], Any]

# 教育部 2026 指导意见口径；库里 detect_scenario_threshold 可被运营改，这里只作兜底与说明
POLICY_LINES = {
    "academic_bachelor": ("本科", 20),
    "academic_master": ("硕士", 15),
    "academic_phd": ("博士", 10),
    "job_report": ("职业报告", 15),
    "self_media": ("自媒体", 30),
    "other": ("其他", 25),
}

# 各维「更像人」的方向：+1 值越大越像人，-1 值越小越像人，0 无方向（对比修改稿时用）
SURFACE_HUMAN_DIR = {
    "sent_len_cv": 1, "discourse_marker_rate": -1, "ttr": 1, "punct_gap_cv": 1,
    "hapax_ratio": 1, "char_entropy": 1, "repeat_bigram_rate": -1, "avg_sent_len": 0,
}

# 表层特征里最适合翻成人话的几维（名称 → (人话标签, 高值含义, 低值含义)）
SURFACE_EXPLAIN = {
    "sent_len_cv": ("句长变化", "长短句交错，节奏像人写", "句子长度很匀，是机器文本常见的『平』"),
    "discourse_marker_rate": ("套话连接词", "『首先/综上所述/值得注意的是』这类词偏多，模板感强", "连接词少，表达更直接"),
    "ttr": ("用词丰富度", "词汇多样", "词汇重复、变化少"),
    "punct_gap_cv": ("标点节奏", "停顿长短不一，有呼吸感", "标点间隔很规律"),
    "hapax_ratio": ("只出现一次的词占比", "细节词多、具体", "反复用同一批词"),
    "char_entropy": ("用字多样性", "用字分散", "用字集中"),
    "repeat_bigram_rate": ("重复搭配", "固定搭配反复出现", "搭配不重复"),
    "avg_sent_len": ("平均句长", "句子偏长", "句子偏短"),
}


# 证据基线来源 → 给用户看的限定语；翻译时必须带，避免「比人类更平」这种越权表述
EVIDENCE_BASIS_LABEL = {
    "checkpoint": "相对训练集文本分布（模型自带基线）",
    "baseline": "相对通用中文论文基线（外置统计）",
    "document": "相对本文其它正文段落",
}
_BASELINE_CACHE: dict[str, Any] = {}


@dataclass
class ToolResult:
    ok: bool
    data: Any = None
    summary: str = ""      # 给 tool_result 事件与审计用的一句话
    error: str = ""

    def to_model_content(self) -> str:
        if not self.ok:
            return json.dumps({"error": self.error}, ensure_ascii=False)
        return json.dumps(self.data, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "get_task_detail",
        "description": "加载一次检测任务的报告：整体 AI 率、场景与红线阈值、每段的 AI 概率与来源标签。用户问『我这次结果怎么样』『哪几段有问题』时先调它。",
        "parameters": {"type": "object", "properties": {"task_id": {"type": "integer", "description": "任务 id；不传则用当前对话绑定的任务"}}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "list_my_tasks",
        "description": "列出用户最近的检测任务（标题、AI 率、时间、状态）。用户问『我上次测的』『测了几次』时用。",
        "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "default": 5}}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "explain_paragraph",
        "description": "解释某一段为什么被判为 AI/人类：返回该段的校准概率、来源标签、告警，以及句长节奏、套话连接词、用词丰富度等表层特征的偏离方向。回答『为什么第 N 段像 AI』必须先调它，并引用返回的具体数值。",
        "parameters": {"type": "object", "properties": {
            "task_id": {"type": "integer"},
            "paragraph_idx": {"type": "integer", "description": "段落序号，从 0 起；用户说『第 3 段』通常是 idx=2"},
        }, "required": ["paragraph_idx"]},
    }},
    {"type": "function", "function": {
        "name": "detect_text",
        "description": "对用户粘贴的一段文字即时做 AI 检测，返回校准概率与可靠性提示。少于 120 字结果不可靠，要如实告知。",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    }},
    {"type": "function", "function": {
        "name": "get_threshold_policy",
        "description": "查询某个场景（本科/硕士/博士/职业报告/自媒体）的 AI 率红线阈值与政策依据。用户问『多少算过』『硕士红线』时用。",
        "parameters": {"type": "object", "properties": {"scenario": {"type": "string", "description": "academic_bachelor | academic_master | academic_phd | job_report | self_media | other，也可传中文如『硕士』"}}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "search_knowledge",
        "description": "检索知识库：检测原理、校准与置信区间、为什么规范化学术文体容易被误判、答辩材料清单、学术规范、申诉流程、人类写作特征。用户问原理性或流程性问题时用。",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "compare_revision",
        "description": "修改稿 vs 上一次检测：整体 AI 率变化、逐段概率变化，以及每段表层特征（句长节奏 / 套话连接词 / 用词丰富度 / 标点节奏等）的前后差值和方向（更像人 / 更像机器）。用户问『我改的方向对了吗』『改了之后有进步吗』『哪几段白改了』时用。只有当前任务是修改稿（有 parentTaskId）才能比。",
        "parameters": {"type": "object", "properties": {"task_id": {"type": "integer", "description": "修改稿任务 id；不传则用当前对话绑定的任务"}}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "create_appeal",
        "description": "对某次检测结果发起人工复核申诉。只有在用户明确说『申诉/复核/我要提交』并给出理由后才调用；调用前要先向用户复述理由并确认。",
        "parameters": {"type": "object", "properties": {
            "task_id": {"type": "integer"},
            "reason": {"type": "string", "description": "用户的申诉理由，原样转述"},
            "paragraph_idxs": {"type": "array", "items": {"type": "integer"},
                               "description": "用户认为判错的段落序号（0 起），能确定时必填"},
            "consent_improve": {"type": "boolean",
                                "description": "用户是否同意把勾选段落用于改进模型（只做评测、不公开）；必须明确问过用户才传 true"},
        }, "required": ["reason"]},
    }},
]

TOOL_LABELS = {
    "get_task_detail": "正在读取检测报告…",
    "list_my_tasks": "正在查看你的检测记录…",
    "explain_paragraph": "正在分析这一段…",
    "detect_text": "正在检测这段文字…",
    "get_threshold_policy": "正在查阈值…",
    "search_knowledge": "正在查资料…",
    "create_appeal": "正在提交申诉…",
    "compare_revision": "正在对比修改前后…",
}

_SCENARIO_ALIAS = {
    "本科": "academic_bachelor", "学士": "academic_bachelor", "bachelor": "academic_bachelor",
    "硕士": "academic_master", "研究生": "academic_master", "master": "academic_master",
    "博士": "academic_phd", "phd": "academic_phd",
    "职业": "job_report", "报告": "job_report", "工作": "job_report",
    "自媒体": "self_media", "公众号": "self_media",
}


def normalize_scenario(s: Optional[str]) -> str:
    if not s:
        return "other"
    s = s.strip().lower()
    if s in POLICY_LINES:
        return s
    for k, v in _SCENARIO_ALIAS.items():
        if k in s:
            return v
    return "other"


# ---------------------------------------------------------------------------
# 执行器
# ---------------------------------------------------------------------------

class ToolRunner:
    def __init__(self, detector_getter: DetectorGetter, user_id: Optional[int], default_task_id: Optional[int]) -> None:
        self._get_detector = detector_getter
        self.user_id = user_id
        self.default_task_id = default_task_id
        self._task_cache: dict[int, dict[str, Any]] = {}

    # ---- Java 调用 ----
    async def _java(self, method: str, path: str, **kw) -> Any:
        url = f"{CONFIG.java_base_url.rstrip('/')}{path}"
        headers = {"X-Assistant-Internal": "1"}
        if self.user_id is not None:
            headers["X-User-Id"] = str(self.user_id)
        async with httpx.AsyncClient(timeout=CONFIG.java_timeout_s) as c:
            r = await c.request(method, url, headers=headers, **kw)
        r.raise_for_status()
        body = r.json()
        # 若依 R 结构 {code, msg, data}
        if isinstance(body, dict) and "code" in body:
            if body.get("code") not in (0, 200):
                raise RuntimeError(body.get("msg") or f"业务错误 {body.get('code')}")
            return body.get("data")
        return body

    def _resolve_task_id(self, args: dict[str, Any]) -> Optional[int]:
        tid = args.get("task_id") or self.default_task_id
        return int(tid) if tid is not None else None

    async def run(self, name: str, raw_args: str) -> ToolResult:
        try:
            args = json.loads(raw_args) if raw_args.strip() else {}
        except json.JSONDecodeError:
            return ToolResult(ok=False, error="参数不是合法 JSON", summary="参数解析失败")
        fn = getattr(self, f"tool_{name}", None)
        if fn is None:
            return ToolResult(ok=False, error=f"未知工具 {name}", summary="未知工具")
        try:
            return await fn(args)
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            msg = {401: "未登录或登录已失效", 403: "没有权限查看该任务", 404: "任务不存在"}.get(code, f"业务服务返回 {code}")
            return ToolResult(ok=False, error=msg, summary=msg)
        except httpx.HTTPError as e:
            log.warning("工具 %s 调 Java 失败: %s", name, e)
            return ToolResult(ok=False, error="业务服务暂时不可用", summary="业务服务不可用")
        except Exception as e:
            log.exception("工具 %s 执行异常", name)
            return ToolResult(ok=False, error=f"执行失败：{type(e).__name__}", summary="工具执行失败")

    # ---- 7 工具 ----
    async def tool_get_task_detail(self, args: dict[str, Any]) -> ToolResult:
        tid = self._resolve_task_id(args)
        if tid is None:
            return ToolResult(ok=False, error="没有指定任务。请让用户说明是哪次检测，或从报告页进入。", summary="缺少任务 id")
        detail = await self._fetch_task(tid)
        paras = detail.get("paragraphs") or []
        body = [p for p in paras if not p.get("excluded")]
        top = sorted(body, key=lambda p: -(p.get("calibratedProb") or 0))[:5]
        data = {
            "taskId": tid,
            "title": detail.get("paperTitle"),
            "status": detail.get("status"),
            "scenario": detail.get("scenario"),
            "threshold": detail.get("threshold"),
            "aiRate": detail.get("aiRate"),
            "overThreshold": (detail.get("aiRate") is not None and detail.get("threshold") is not None
                              and detail["aiRate"] > detail["threshold"]),
            "wordCount": detail.get("wordCount"),
            "bodyParagraphs": len(body),
            "excludedParagraphs": detail.get("excludedParagraphCount"),
            "sourceLabels": detail.get("sourceLabels"),
            "modelVersion": detail.get("modelVersion"),
            # 复测对比：有上一次就给助手讲「进步了多少」；版本不同要提醒不可直接比
            "parentTaskId": detail.get("parentTaskId"),
            "parentAiRate": detail.get("parentAiRate"),
            "parentModelVersion": detail.get("parentModelVersion"),
            "topRiskParagraphs": [
                {"idx": p.get("paragraphIdx"), "calibratedProb": p.get("calibratedProb"),
                 "sourceLabel": p.get("sourceLabel"), "preview": (p.get("text") or "")[:60]}
                for p in top
            ],
            "riskBuckets": {
                "red(>=0.7)": sum(1 for p in body if (p.get("calibratedProb") or 0) >= 0.7),
                "yellow(0.4-0.7)": sum(1 for p in body if 0.4 <= (p.get("calibratedProb") or 0) < 0.7),
                "green(<0.4)": sum(1 for p in body if (p.get("calibratedProb") or 0) < 0.4),
            },
        }
        s = f"AI 率 {data['aiRate']}%，阈值 {data['threshold']}%，红段 {data['riskBuckets']['red(>=0.7)']} 个"
        return ToolResult(ok=True, data=data, summary=s)

    async def _fetch_task(self, tid: int) -> dict[str, Any]:
        if tid in self._task_cache:
            return self._task_cache[tid]
        detail = await self._java("GET", f"/api/v1/detect/tasks/{tid}")
        if not isinstance(detail, dict):
            raise RuntimeError("任务详情格式异常")
        self._task_cache[tid] = detail
        return detail

    async def tool_list_my_tasks(self, args: dict[str, Any]) -> ToolResult:
        limit = int(args.get("limit") or 5)
        params = {"pageNum": 1, "pageSize": min(max(limit, 1), 20)}
        if self.user_id is not None:
            params["userId"] = self.user_id
        page = await self._java("GET", "/api/v1/detect/tasks", params=params)
        rows = (page or {}).get("rows") or (page or {}).get("list") or (page if isinstance(page, list) else [])
        data = [{"taskId": r.get("id"), "title": r.get("paperTitle"), "aiRate": r.get("aiRate"),
                 "parentTaskId": r.get("parentTaskId"),
                 "threshold": r.get("threshold"), "scenario": r.get("scenario"), "status": r.get("status"),
                 "createdAt": r.get("createdAt")} for r in rows[:limit]]
        return ToolResult(ok=True, data=data, summary=f"最近 {len(data)} 条记录")

    async def tool_explain_paragraph(self, args: dict[str, Any]) -> ToolResult:
        tid = self._resolve_task_id(args)
        if tid is None:
            return ToolResult(ok=False, error="没有指定任务", summary="缺少任务 id")
        idx = int(args.get("paragraph_idx", -1))
        detail = await self._fetch_task(tid)
        paras = detail.get("paragraphs") or []
        para = next((p for p in paras if p.get("paragraphIdx") == idx), None)
        if para is None:
            return ToolResult(ok=False, error=f"没有第 {idx} 段（共 {len(paras)} 段，序号从 0 起）", summary="段落不存在")
        if para.get("excluded"):
            return ToolResult(ok=True, data={"paragraphIdx": idx, "excluded": True, "reason": para.get("excludeReason"),
                                             "note": "这段被识别为非正文（参考文献/致谢/标题等），不参与 AI 率计算"},
                              summary="非正文段，未参与判定")
        text = para.get("text") or ""
        data: dict[str, Any] = {
            "paragraphIdx": idx,
            "calibratedProb": para.get("calibratedProb"),
            "rawProb": para.get("aiProb"),
            "sourceLabel": para.get("sourceLabel"),
            "warnings": para.get("warnings") or [],
            "chars": len(text),
            "preview": text[:80],
            "verdict": _verdict(para.get("calibratedProb")),
            "sentences": [
                {"idx": s.get("sentenceIdx"), "aiProb": s.get("aiProb"), "text": (s.get("text") or "")[:40]}
                for s in sorted(para.get("sentences") or [], key=lambda s: -(s.get("aiProb") or 0))[:3]
            ],
        }
        if len(text) < 120:
            data["reliability"] = f"该段只有 {len(text)} 字，低于 120 字可靠判定门槛，结论仅供参考"
        det = self._get_detector()
        refs = [p.get("text") or "" for p in paras if not p.get("excluded") and p.get("paragraphIdx") != idx]
        _attach_surface_evidence(data, det, text, refs)
        return ToolResult(ok=True, data=data, summary=f"第 {idx} 段 校准概率 {data['calibratedProb']}，{data['verdict']}")

    async def tool_compare_revision(self, args: dict[str, Any]) -> ToolResult:
        tid = self._resolve_task_id(args)
        if tid is None:
            return ToolResult(ok=False, error="没有指定任务", summary="缺少任务 id")
        detail = await self._fetch_task(tid)
        parent_id = detail.get("parentTaskId")
        if not parent_id:
            return ToolResult(ok=False, error="这次检测不是修改稿（上传时没有关联上一次），没有可对比的版本；下次上传时在「这是修改稿？」里选上一次即可",
                              summary="无上一次版本")
        cmp = await self._java("GET", f"/api/v1/detect/tasks/{tid}/compare")
        parent = await self._fetch_task(int(parent_id))
        cur_map = {p.get("paragraphIdx"): p for p in (detail.get("paragraphs") or [])}
        par_map = {p.get("paragraphIdx"): p for p in (parent.get("paragraphs") or [])}
        rows = cmp.get("rows") or []
        summary = cmp.get("summary") or {}

        paired: list[dict[str, Any]] = []
        agg: dict[str, list[float]] = {k: [] for k in SURFACE_HUMAN_DIR}
        for r in rows:
            ci, pi = r.get("currIdx"), r.get("parentIdx")
            if ci is None or pi is None:
                continue
            cur, par = cur_map.get(ci), par_map.get(pi)
            if not cur or not par:
                continue
            changes = _surface_changes(par.get("text") or "", cur.get("text") or "")
            for ch in changes:
                agg[ch["name"]].append(ch["delta"])
            delta = r.get("delta")
            if delta is None and cur.get("calibratedProb") is not None and par.get("calibratedProb") is not None:
                delta = cur["calibratedProb"] - par["calibratedProb"]
            toward = sum(1 for ch in changes if ch["towardHuman"])
            away = sum(1 for ch in changes if ch["towardHuman"] is False)
            if delta is None:
                verdict = "无法判断"
            elif delta <= -0.1:
                verdict = "有效"
            elif delta >= 0.1:
                verdict = "反了"
            elif r.get("status") == "same":
                verdict = "没动"
            else:
                verdict = "变化不大"
            paired.append({
                "currIdx": ci, "parentIdx": pi, "status": r.get("status"),
                "parentProb": r.get("parentProb"), "currProb": r.get("currProb"), "delta": None if delta is None else round(delta, 3),
                "verdict": verdict, "towardHuman": toward, "awayFromHuman": away,
                "preview": (cur.get("text") or "")[:50],
                "changes": [c for c in changes if c["notable"]][:3],
            })
        # 改动最大的段放前面；没改的高风险段单列
        paired.sort(key=lambda p: -abs(p["delta"] or 0))
        untouched = [p for p in paired if p["status"] == "same" and (p.get("currProb") or 0) >= 0.5]
        overall = []
        for name, deltas in agg.items():
            if not deltas or SURFACE_HUMAN_DIR[name] == 0:
                continue
            mean = sum(deltas) / len(deltas)
            label, hi, lo = SURFACE_EXPLAIN[name]
            toward = (mean > 0 and SURFACE_HUMAN_DIR[name] > 0) or (mean < 0 and SURFACE_HUMAN_DIR[name] < 0)
            overall.append({"feature": label, "meanDelta": round(mean, 4), "direction": "更像人" if toward else "更像机器",
                            "reading": (hi if mean > 0 else lo)})
        overall.sort(key=lambda o: -abs(o["meanDelta"]))

        changed = [p for p in paired if p["status"] in ("down", "up")]
        effective = sum(1 for p in paired if p["verdict"] == "有效")
        reversed_ = sum(1 for p in paired if p["verdict"] == "反了")
        if not changed and not summary.get("added"):
            direction = "基本没改"
        elif effective and not reversed_:
            direction = "方向对了"
        elif effective > reversed_:
            direction = "大部分对了"
        elif reversed_:
            direction = "方向反了"
        else:
            direction = "变化不大"

        data = {
            "currentTaskId": tid, "parentTaskId": parent_id,
            "aiRate": detail.get("aiRate"), "parentAiRate": parent.get("aiRate"),
            "deltaRate": summary.get("deltaRate"), "threshold": detail.get("threshold"), "pass": summary.get("pass"),
            "comparable": cmp.get("comparable", True), "modelChanged": detail.get("modelVersion") != parent.get("modelVersion"),
            "summary": {k: summary.get(k) for k in ("down", "up", "added", "removed", "changed")},
            "direction": direction, "effectiveParagraphs": effective, "reversedParagraphs": reversed_,
            "overallChanges": overall[:4],
            "paragraphs": paired[:6],
            "untouchedHighRisk": [{"currIdx": p["currIdx"], "currProb": p["currProb"], "preview": p["preview"]} for p in untouched[:4]],
            "evidenceBasis": "表层特征取修改前后同一段的原始值直接相减，不依赖训练集基线",
        }
        s = f"AI 率 {parent.get('aiRate')}% → {detail.get('aiRate')}%，{direction}，有效 {effective} 段、反了 {reversed_} 段"
        return ToolResult(ok=True, data=data, summary=s)

    async def tool_detect_text(self, args: dict[str, Any]) -> ToolResult:
        text = (args.get("text") or "").strip()
        if not text:
            return ToolResult(ok=False, error="文本为空", summary="文本为空")
        det = self._get_detector()
        if det is None:
            return ToolResult(ok=False, error="检测模型未加载，当前无法即时检测", summary="模型未加载")
        pred = det.predict_paragraph(text[:1600], with_sentences=False)
        data = {
            "chars": len(text), "calibratedProb": pred.calibrated_prob, "rawProb": pred.ai_prob,
            "verdict": _verdict(pred.calibrated_prob), "modelVersion": pred.model_version,
            "warning": pred.warning or ("" if len(text) >= 120 else f"仅 {len(text)} 字，结果不可靠"),
        }
        _attach_surface_evidence(data, det, text, [])
        return ToolResult(ok=True, data=data, summary=f"校准概率 {pred.calibrated_prob}，{data['verdict']}")

    async def tool_get_threshold_policy(self, args: dict[str, Any]) -> ToolResult:
        sc = normalize_scenario(args.get("scenario"))
        label, default_line = POLICY_LINES[sc]
        data: dict[str, Any] = {"scenario": sc, "label": label, "threshold": default_line, "source": "教育部 2026 指导意见默认值"}
        try:
            # Java 侧场景阈值表可被运营调整，优先用它
            rows = await self._java("GET", "/api/v1/detect/scenario-thresholds")
            if isinstance(rows, list):
                hit = next((r for r in rows if r.get("scenario") == sc), None)
                if hit and hit.get("threshold") is not None:
                    data["threshold"] = float(hit["threshold"])
                    data["source"] = "平台当前生效阈值"
        except Exception:
            pass   # 端点未实现或不可达时用默认值，不阻断
        data["note"] = "各校可能有更严格的内部规定（如人大 >30% 不予通过），以学校最新通知为准；红线比较的是校准后的整体 AI 率"
        hits = get_kb().search(f"{label} 红线 政策", top_k=1)
        if hits:
            data["policyExcerpt"] = hits[0][0].text[:400]
        return ToolResult(ok=True, data=data, summary=f"{label} 红线 {data['threshold']}%")

    async def tool_search_knowledge(self, args: dict[str, Any]) -> ToolResult:
        q = (args.get("query") or "").strip()
        hits = get_kb().search(q)
        if not hits:
            return ToolResult(ok=True, data={"hits": [], "note": "知识库没有直接相关内容，请基于常识谨慎回答并说明不确定"}, summary="无命中")
        data = {"hits": [{"ref": c.ref, "text": c.text[:600]} for c, _ in hits]}
        return ToolResult(ok=True, data=data, summary=f"命中 {len(hits)} 条：{hits[0][0].title}")

    async def tool_create_appeal(self, args: dict[str, Any]) -> ToolResult:
        tid = self._resolve_task_id(args)
        reason = (args.get("reason") or "").strip()
        if tid is None:
            return ToolResult(ok=False, error="没有指定任务", summary="缺少任务 id")
        if len(reason) < 5:
            return ToolResult(ok=False, error="申诉理由太短，请让用户补充", summary="理由不足")
        payload = {"category": "appeal", "taskId": tid, "content": reason[:2000]}
        idxs = args.get("paragraph_idxs")
        if isinstance(idxs, list) and idxs:
            payload["paragraphIdxs"] = [int(i) for i in idxs if isinstance(i, (int, float))][:50]
        if args.get("consent_improve") is True:
            payload["consentImprove"] = True
        if self.user_id is not None:
            payload["userId"] = self.user_id
        res = await self._java("POST", "/api/v1/feedback", json=payload)
        fid = (res or {}).get("id") if isinstance(res, dict) else res
        return ToolResult(ok=True, data={"feedbackId": fid, "taskId": tid, "status": "PENDING",
                                         "next": "运营会人工复核，结果在『我的反馈』里查看"},
                          summary=f"申诉已提交 #{fid}")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _verdict(p: Optional[float]) -> str:
    if p is None:
        return "无结果"
    if p >= 0.7:
        return "高风险（红）"
    if p >= 0.4:
        return "中风险（黄）"
    return "低风险（绿）"


def _surface_changes(before: str, after: str) -> list[dict[str, Any]]:
    """同一段修改前后的 8 维可解释表层特征差值；相对变化 ≥ 15% 记为 notable。"""
    if not _SURFACE_OK or not before.strip() or not after.strip():
        return []
    try:
        fb = extract_surface_features(before)
        fa = extract_surface_features(after)
    except Exception:
        return []
    idx = {n: i for i, n in enumerate(SURFACE_FEATURE_NAMES)}
    out = []
    for name, (label, hi, lo) in SURFACE_EXPLAIN.items():
        if name not in idx:
            continue
        b, a = float(fb[idx[name]]), float(fa[idx[name]])
        delta = a - b
        rel = abs(delta) / (abs(b) + 1e-6)
        d = SURFACE_HUMAN_DIR.get(name, 0)
        toward = None if d == 0 or abs(delta) < 1e-9 else ((delta > 0) == (d > 0))
        out.append({
            "name": name, "feature": label, "before": round(b, 4), "after": round(a, 4), "delta": round(delta, 4),
            "towardHuman": toward, "notable": rel >= 0.15,
            "direction": "更像人" if toward else ("更像机器" if toward is False else "中性"),
            "reading": (hi if delta > 0 else lo) if abs(delta) > 1e-9 else "没变",
        })
    out.sort(key=lambda c: -abs(c["delta"]) / (abs(c["before"]) + 1e-6))
    return out


def _external_baseline():
    """TEXT_SURFACE_BASELINE_PATH 指向的外置基线，进程内只读一次。"""
    if "scaler" not in _BASELINE_CACHE:
        _BASELINE_CACHE["scaler"] = load_surface_baseline(CONFIG.surface_baseline_path) if _SURFACE_OK else None
    return _BASELINE_CACHE["scaler"]


def _surface_zscores(det: Any, text: str, references: list[str]) -> tuple[Optional[dict[str, float]], str]:
    """三级基线：fusion checkpoint 自带 scaler > 外置基线文件 > 同一篇文章其它正文段。返回 (z, basis)。"""
    if det is not None:
        try:
            z = det.surface_profile(text)   # cls_only 模型返回 None
        except Exception:
            z = None
        if z:
            return z, "checkpoint"
    if not _SURFACE_OK:
        return None, ""
    scaler = _external_baseline()
    if scaler is not None:
        z = scaler.transform(extract_surface_features(text)[None])[0]
        return {n: float(v) for n, v in zip(SURFACE_FEATURE_NAMES, z)}, "baseline"
    z = document_baseline_zscores(text, references) if references else None
    return (z, "document") if z else (None, "")


def _attach_surface_evidence(data: dict[str, Any], det: Any, text: str, references: list[str]) -> None:
    """往工具结果里塞 surfaceEvidence / evidenceBasis / surfaceFacts；三者都没有时给一句说明。"""
    z, basis = _surface_zscores(det, text, references)
    profile = _surface_profile(z)
    if profile:
        data["surfaceEvidence"] = profile
        data["evidenceBasis"] = EVIDENCE_BASIS_LABEL.get(basis, basis)
        data["evidenceBasisKey"] = basis
    elif z:
        data["surfaceEvidence"] = f"表层特征{EVIDENCE_BASIS_LABEL.get(basis, basis)}没有明显偏离，像 AI 的判断主要来自语义层面，不是句长或套话"
        data["evidenceBasisKey"] = basis
    else:
        data["surfaceEvidence"] = (
            "当前模型没有表层特征基线，且这篇文章正文段太少，无法做段落间对比；只能基于概率和下面的事实读数解释"
            if _SURFACE_OK else "当前服务未启用表层特征，只能基于概率解释"
        )
    if _SURFACE_OK:
        try:
            data["surfaceFacts"] = surface_facts(text)
        except Exception:
            pass


def _surface_profile(z: Optional[dict[str, float]]) -> Optional[list[dict[str, Any]]]:
    """把 30 维 z-score 挑最偏离的几维翻成人话。"""
    if not z:
        return None
    items = []
    for name, (label, hi, lo) in SURFACE_EXPLAIN.items():
        if name not in z:
            continue
        v = float(z[name])
        if abs(v) < 0.8:
            continue
        items.append({"feature": label, "zscore": round(v, 2), "reading": hi if v > 0 else lo})
    items.sort(key=lambda d: -abs(d["zscore"]))
    return items[:4] or None
