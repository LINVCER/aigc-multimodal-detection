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

音频检测：detectors/audio.py 骨架就位，加载 & predict 实现待 Wave 5 训练启动后填充；
未加载时 /api/v1/detect/audio 走 MD5 stub 兜底。图像检测 Wave 5 议。
"""
from __future__ import annotations

import hashlib
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from pydantic import BaseModel

from detectors.audio import AudioAIGCDetector
from detectors.text import TextAIGCDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
log = logging.getLogger("inference")


# ==========================================================
# 单例检测器
# ==========================================================

text_detector: TextAIGCDetector | None = None
text_load_error: str | None = None
audio_detector: AudioAIGCDetector | None = None
audio_load_error: str | None = None


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


def _bootstrap_audio_detector() -> None:
    global audio_detector, audio_load_error
    base = os.getenv("AUDIO_BASE_MODEL_PATH", "").strip()
    ckpt = os.getenv("AUDIO_CHECKPOINT_PATH", "").strip()
    if not base or not ckpt or not os.path.exists(ckpt):
        audio_load_error = "AUDIO_BASE_MODEL_PATH / AUDIO_CHECKPOINT_PATH 未就绪，fallback stub（Wave 5 待接入）"
        log.info(audio_load_error)
        return
    try:
        detector = AudioAIGCDetector(
            base_model_path=base,
            checkpoint_path=ckpt,
            device=os.getenv("AUDIO_DEVICE", "cpu"),
            window_sec=float(os.getenv("AUDIO_WINDOW_SEC", "3.0")),
            stride_sec=float(os.getenv("AUDIO_STRIDE_SEC", "1.0")),
            model_version=os.getenv("AUDIO_MODEL_VERSION", "audio_v0"),
        )
        detector.load()
        audio_detector = detector
        audio_load_error = None
        log.info("audio detector activated")
    except Exception as e:
        audio_load_error = f"加载失败：{type(e).__name__}: {e}"
        log.exception("audio detector load failed, fallback stub")


@asynccontextmanager
async def lifespan(_: FastAPI):
    _bootstrap_text_detector()
    _bootstrap_audio_detector()
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
        "audio": {
            "backend": "real" if audio_detector else "stub",
            "load_error": audio_load_error,
            "detail": audio_detector.health() if audio_detector else None,
        },
    }


@app.post("/api/v1/detect/paragraph", response_model=DetectParagraphResponse)
def detect_paragraph(req: DetectParagraphRequest) -> DetectParagraphResponse:
    return _detect_one(req)


@app.post("/api/v1/detect/audio")
def detect_audio(
    file: UploadFile = File(...),
    return_segments: str = Form("true"),
) -> dict[str, Any]:
    """
    音频 AI 检测（Wave 5 骨架 · 当前走 stub 兜底）

    多部分表单：
      - file: 音频文件（mp3/wav/m4a/flac/ogg/webm）
      - return_segments: "true" / "false"

    返回 schema（跟 Java 端 AudioSegmentResult / DetectTaskDetailVO 对齐）：
      { ai_prob, calibrated_prob, duration_sec, model_version, segments: [
          { segment_idx, time_start, time_end, ai_prob, calibrated_prob, waveform_peak? }
      ]}
    """
    want_seg = str(return_segments).lower() == "true"
    audio_bytes = file.file.read()

    if audio_detector is not None:
        try:
            pred = audio_detector.predict(audio_bytes, file.filename or "audio.bin")
            return {
                "ai_prob": round(pred.ai_prob, 4),
                "calibrated_prob": round(pred.calibrated_prob, 4),
                "duration_sec": round(pred.duration_sec, 2),
                "model_version": pred.model_version,
                "segments": [
                    {
                        "segment_idx": s.segment_idx,
                        "time_start": round(s.time_start, 2),
                        "time_end": round(s.time_end, 2),
                        "ai_prob": round(s.ai_prob, 4),
                        "calibrated_prob": round(s.calibrated_prob, 4),
                        "source_label": s.source_label,
                        "waveform_peak": s.waveform_peak,
                    }
                    for s in pred.segments
                ] if want_seg else [],
            }
        except NotImplementedError:
            log.info("audio detector loaded but predict() unimplemented, fallback stub")
        except Exception:
            log.exception("audio real inference failed, fallback stub")

    return _audio_stub(audio_bytes, file.filename or "audio.bin", want_seg)


def _audio_stub(audio_bytes: bytes, filename: str, want_seg: bool) -> dict[str, Any]:
    """确定性 stub：MD5 取模生成假 ai_prob + 假 duration_sec + 假 segments"""
    h = hashlib.md5((filename + str(len(audio_bytes))).encode()).digest()
    seed = int.from_bytes(h[:4], "big") / 0xFFFFFFFF
    duration = 15.0 + (int.from_bytes(h[4:6], "big") % 600) / 10.0   # 15-75s
    ai_prob = seed
    calibrated = min(1.0, max(0.0, ai_prob * 0.9 + 0.05))

    segments = []
    if want_seg:
        window, stride = 3.0, 1.0
        t = 0.0
        idx = 0
        while t < duration:
            end = min(t + window, duration)
            local = _deterministic_prob(f"{filename}|{idx}", "aud")
            local_cal = min(1.0, max(0.0, local * 0.9 + 0.05))
            segments.append({
                "segment_idx": idx,
                "time_start": round(t, 2),
                "time_end": round(end, 2),
                "ai_prob": round(local, 4),
                "calibrated_prob": round(local_cal, 4),
                "source_label": "tts" if local >= 0.7 else ("cloned_voice" if local >= 0.4 else "real_human"),
                "waveform_peak": round(0.3 + _deterministic_prob(f"{filename}|peak|{idx}") * 0.6, 3),
            })
            idx += 1
            t += stride

    return {
        "ai_prob": round(ai_prob, 4),
        "calibrated_prob": round(calibrated, 4),
        "duration_sec": round(duration, 2),
        "model_version": "audio-stub-v0",
        "segments": segments,
    }


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
