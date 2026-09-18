"""
Phase 0 → Phase 1 推理服务
==========================

启动时尝试加载真实文本模型（chinese-roberta-wwm-ext + aigc_detector_v3_thesis.pth）；
加载成功 → detect_paragraph 走真实推理；失败 → 自动 fallback 到 MD5 stub（服务不 down）。

env / .env 配置：
    TEXT_BASE_MODEL_PATH   基座 roberta 路径（本地 dir 或 HF repo id）
    TEXT_CHECKPOINT_PATH   训练权重 .pth 绝对路径
    TEXT_DEVICE            cpu / cuda:0
    TEXT_MAX_LENGTH        512（可被 checkpoint.hyperparams 覆盖）
    TEXT_MODEL_VERSION     报给前端的版本标签

图像 / 音频 / 篡改检测暂 stub，Wave 4 后续 batch 补。
"""
from __future__ import annotations

import hashlib
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from detectors.text import TextAIGCDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
log = logging.getLogger("inference")


# ==========================================================
# 单例检测器
# ==========================================================

text_detector: TextAIGCDetector | None = None
text_load_error: str | None = None


def _bootstrap_text_detector() -> None:
    global text_detector, text_load_error
    base = os.getenv("TEXT_BASE_MODEL_PATH", "").strip()
    ckpt = os.getenv("TEXT_CHECKPOINT_PATH", "").strip()
    if not base or not ckpt:
        text_load_error = "TEXT_BASE_MODEL_PATH / TEXT_CHECKPOINT_PATH 未设置，fallback stub"
        log.warning(text_load_error)
        return
    if not os.path.exists(ckpt):
        text_load_error = f"checkpoint 不存在：{ckpt}，fallback stub"
        log.warning(text_load_error)
        return

    try:
        detector = TextAIGCDetector(
            base_model_path=base,
            checkpoint_path=ckpt,
            device=os.getenv("TEXT_DEVICE", "cpu"),
            max_length=int(os.getenv("TEXT_MAX_LENGTH", "512")),
            model_version=os.getenv("TEXT_MODEL_VERSION", "aigc_v3_thesis"),
        )
        detector.load()
        text_detector = detector
        text_load_error = None
        log.info("text detector activated, real inference enabled")
    except Exception as e:
        text_load_error = f"加载失败：{type(e).__name__}: {e}"
        log.exception("text detector load failed, fallback stub")


@asynccontextmanager
async def lifespan(_: FastAPI):
    _bootstrap_text_detector()
    yield
    # no explicit teardown


app = FastAPI(title="paperaigc-inference", version="0.2.0", lifespan=lifespan)


# ==========================================================
# 请求 / 响应（与 backend-java proto 对齐）
# ==========================================================

class DetectParagraphRequest(BaseModel):
    text: str
    model_version: str | None = None
    return_calibrated: bool = True
    return_sentences: bool = False


class SentenceScore(BaseModel):
    sentence_idx: int
    offset_start: int
    offset_end: int
    ai_prob: float


class DetectParagraphResponse(BaseModel):
    ai_prob: float
    calibrated_prob: float
    interval: dict[str, float]
    risk_level: str
    warning: str = ""
    branch_scores: dict[str, float]
    sentences: list[SentenceScore] = []
    model_version: str = "stub-v0"


class DetectBatchRequest(BaseModel):
    items: list[DetectParagraphRequest]


class DetectBatchResponse(BaseModel):
    items: list[DetectParagraphResponse]


class HumanizeRequest(BaseModel):
    text: str
    style: str = "academic"
    model_version: str | None = None


class HumanizeResponse(BaseModel):
    rewritten_text: str
    quality_score: float
    model_version: str = "stub-v0"


class AttributeRequest(BaseModel):
    text: str


class AttributeResponse(BaseModel):
    source_probs: dict[str, float]
    top_source: str


# ==========================================================
# helpers
# ==========================================================

def _risk_level(prob: float) -> str:
    return "high" if prob >= 0.7 else ("medium" if prob >= 0.4 else "low")


def _deterministic_prob(text: str, salt: str = "") -> float:
    h = hashlib.md5((salt + text).encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") / 0xFFFFFFFF


def _stub_split(text: str) -> list[tuple[int, int, str]]:
    out: list[tuple[int, int, str]] = []
    start, cursor = 0, 0
    for ch in text:
        cursor += 1
        if ch in "。！？!?." and cursor - start > 5:
            out.append((start, cursor, text[start:cursor]))
            start = cursor
    if start < len(text):
        out.append((start, len(text), text[start:]))
    return out


def _detect_stub(req: DetectParagraphRequest) -> DetectParagraphResponse:
    ai_prob = _deterministic_prob(req.text)
    calibrated = min(1.0, max(0.0, ai_prob * 0.9 + 0.05))
    sentences: list[SentenceScore] = []
    if req.return_sentences:
        for idx, (s, e, sent) in enumerate(_stub_split(req.text)):
            sentences.append(SentenceScore(
                sentence_idx=idx, offset_start=s, offset_end=e,
                ai_prob=round(_deterministic_prob(sent, "sent"), 4),
            ))
    return DetectParagraphResponse(
        ai_prob=round(ai_prob, 4),
        calibrated_prob=round(calibrated, 4),
        interval={"lower": round(max(0, calibrated - 0.08), 4),
                  "upper": round(min(1, calibrated + 0.08), 4)},
        risk_level=_risk_level(calibrated),
        warning="",
        branch_scores={
            "statistical": round(_deterministic_prob(req.text, "stat"), 4),
            "deberta":     round(_deterministic_prob(req.text, "dbrt"), 4),
            "roberta":     round(_deterministic_prob(req.text, "rbrt"), 4),
        },
        sentences=sentences,
        model_version=req.model_version or "stub-v0",
    )


def _detect_real(req: DetectParagraphRequest) -> DetectParagraphResponse:
    assert text_detector is not None
    pred = text_detector.predict_paragraph(req.text, with_sentences=req.return_sentences)
    sentences = [
        SentenceScore(
            sentence_idx=s.sentence_idx,
            offset_start=s.offset_start,
            offset_end=s.offset_end,
            ai_prob=s.calibrated_prob,   # 前端句级用校准后概率打色
        )
        for s in pred.sentences
    ]
    # 置信区间：以校准概率为中心，宽度按 Platt 参数经验值估计
    #   （真实置信区间需要 MC dropout / ensemble，Phase 1 用固定 ±0.06 兜底）
    half = 0.06
    return DetectParagraphResponse(
        ai_prob=pred.ai_prob,
        calibrated_prob=pred.calibrated_prob,
        interval={"lower": round(max(0.0, pred.calibrated_prob - half), 4),
                  "upper": round(min(1.0, pred.calibrated_prob + half), 4)},
        risk_level=_risk_level(pred.calibrated_prob),
        warning="",
        branch_scores={
            # roberta 主分支给校准后；stub 值保留兼容 Wave 2 前端多分支色带
            "roberta":     pred.calibrated_prob,
            "statistical": round(_deterministic_prob(req.text, "stat"), 4),
            "deberta":     round(_deterministic_prob(req.text, "dbrt"), 4),
        },
        sentences=sentences,
        model_version=req.model_version or pred.model_version,
    )


def _detect_one(req: DetectParagraphRequest) -> DetectParagraphResponse:
    if text_detector is not None:
        try:
            return _detect_real(req)
        except Exception:
            log.exception("real inference failed for len=%d, fallback stub", len(req.text or ""))
    return _detect_stub(req)


# ==========================================================
# 路由
# ==========================================================

@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "inference",
        "version": "0.2.0",
        "text": {
            "backend": "real" if text_detector else "stub",
            "load_error": text_load_error,
            "detail": text_detector.health() if text_detector else None,
        },
    }


@app.post("/api/v1/detect/paragraph", response_model=DetectParagraphResponse)
def detect_paragraph(req: DetectParagraphRequest) -> DetectParagraphResponse:
    return _detect_one(req)


@app.post("/api/v1/detect/batch", response_model=DetectBatchResponse)
def detect_batch(req: DetectBatchRequest) -> DetectBatchResponse:
    return DetectBatchResponse(items=[_detect_one(x) for x in req.items])


@app.post("/api/v1/humanize", response_model=HumanizeResponse)
def humanize(req: HumanizeRequest) -> HumanizeResponse:
    # 真实改写模型尚未接入，保留 stub
    rewritten = (req.text
                 .replace("值得注意的是，", "")
                 .replace("综上所述，", "")
                 .replace("首先，", "先说"))
    quality = 0.6 + _deterministic_prob(req.text, "quality") * 0.3
    return HumanizeResponse(rewritten_text=rewritten, quality_score=round(quality, 4))


@app.post("/api/v1/attribute", response_model=AttributeResponse)
def attribute(req: AttributeRequest) -> AttributeResponse:
    # 溯源模型尚未接入，保留 stub
    sources = ["human", "gpt", "claude", "qwen", "deepseek", "glm", "kimi", "ernie", "other"]
    raw = {s: _deterministic_prob(req.text, s) for s in sources}
    total = sum(raw.values())
    probs = {s: round(v / total, 4) for s, v in raw.items()}
    top = max(probs, key=probs.get)
    return AttributeResponse(source_probs=probs, top_source=top)
