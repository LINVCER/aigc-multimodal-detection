"""
Phase 0 推理服务 stub：用 FastAPI mock 提供跟 gRPC proto 语义一致的 HTTP 接口
后续接入真实模型时，本文件被 Triton client / vLLM / FastAPI 白盒服务替换
"""
import hashlib
import random
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="paperaigc-inference-stub", version="0.1.0")

# ---- 请求 / 响应模型（与 backend-java/.../proto/detection.proto 对齐）----

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


# ---- Mock 实现（哈希取模确定性打分，方便 UI 联调）----

def _deterministic_prob(text: str, salt: str = "") -> float:
    h = hashlib.md5((salt + text).encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") / 0xFFFFFFFF


def _split_sentences(text: str) -> list[tuple[int, int, str]]:
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


def _detect_one(req: DetectParagraphRequest) -> DetectParagraphResponse:
    ai_prob = _deterministic_prob(req.text)
    calibrated = min(1.0, max(0.0, ai_prob * 0.9 + 0.05))  # 假装做了 Platt
    if calibrated >= 0.7:
        risk = "high"
    elif calibrated >= 0.4:
        risk = "medium"
    else:
        risk = "low"

    sentences: list[SentenceScore] = []
    if req.return_sentences:
        for idx, (s, e, sent) in enumerate(_split_sentences(req.text)):
            sentences.append(SentenceScore(
                sentence_idx=idx, offset_start=s, offset_end=e,
                ai_prob=round(_deterministic_prob(sent, "sent"), 4),
            ))

    return DetectParagraphResponse(
        ai_prob=round(ai_prob, 4),
        calibrated_prob=round(calibrated, 4),
        interval={"lower": round(max(0, calibrated - 0.08), 4),
                  "upper": round(min(1, calibrated + 0.08), 4)},
        risk_level=risk,
        warning="",
        branch_scores={
            "statistical": round(_deterministic_prob(req.text, "stat"), 4),
            "deberta":     round(_deterministic_prob(req.text, "dbrt"), 4),
            "roberta":     round(_deterministic_prob(req.text, "rbrt"), 4),
        },
        sentences=sentences,
        model_version=req.model_version or "stub-v0",
    )


# ---- 路由 ----

@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "inference-stub", "version": "0.1.0"}


@app.post("/api/v1/detect/paragraph", response_model=DetectParagraphResponse)
def detect_paragraph(req: DetectParagraphRequest) -> DetectParagraphResponse:
    return _detect_one(req)


@app.post("/api/v1/detect/batch", response_model=DetectBatchResponse)
def detect_batch(req: DetectBatchRequest) -> DetectBatchResponse:
    return DetectBatchResponse(items=[_detect_one(x) for x in req.items])


@app.post("/api/v1/humanize", response_model=HumanizeResponse)
def humanize(req: HumanizeRequest) -> HumanizeResponse:
    # stub：句子级简单打乱 + 加口语化词，仅用于 UI 联调
    rewritten = req.text.replace("值得注意的是，", "").replace("综上所述，", "").replace("首先，", "先说")
    quality = 0.6 + _deterministic_prob(req.text, "quality") * 0.3
    return HumanizeResponse(rewritten_text=rewritten, quality_score=round(quality, 4))


@app.post("/api/v1/attribute", response_model=AttributeResponse)
def attribute(req: AttributeRequest) -> AttributeResponse:
    sources = ["human", "gpt", "claude", "qwen", "deepseek", "glm", "kimi", "ernie", "other"]
    raw = {s: _deterministic_prob(req.text, s) for s in sources}
    total = sum(raw.values())
    probs = {s: round(v / total, 4) for s, v in raw.items()}
    top = max(probs, key=probs.get)
    return AttributeResponse(source_probs=probs, top_source=top)
