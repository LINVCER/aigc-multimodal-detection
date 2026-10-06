"""
工具：schema（给模型看）+ 执行器（真干活）。

7 个工具围绕检测场景；唯一写操作 create_appeal 需用户在对话里明确确认。
取业务数据走 Java（鉴权与数据归属在那边），即时检测与表层特征直接用本进程的模型，不绕一圈。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

import httpx

from .config import CONFIG
from .knowledge import get_kb

log = logging.getLogger("assistant.tools")

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
        profile = _surface_profile(det, text)
        if profile:
            data["surfaceEvidence"] = profile
        else:
            data["surfaceEvidence"] = "当前模型未启用表层特征支路，只能基于概率解释"
        return ToolResult(ok=True, data=data, summary=f"第 {idx} 段 校准概率 {data['calibratedProb']}，{data['verdict']}")

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
        profile = _surface_profile(det, text)
        if profile:
            data["surfaceEvidence"] = profile
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


def _surface_profile(det: Any, text: str) -> Optional[list[dict[str, Any]]]:
    """用 fusion 模型自带的 scaler 把 30 维表层特征转成 z-score，挑最偏离的几维翻成人话。"""
    if det is None:
        return None
    try:
        z = det.surface_profile(text)   # {name: zscore}，cls_only 模型返回 None
    except Exception:
        return None
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
