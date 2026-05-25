from typing import Any
from pydantic import BaseModel, Field


class TextDetectionRequest(BaseModel):
    content: str = Field(min_length=1, max_length=50000, examples=["这是一段需要检测的文本内容..."])
    options: dict[str, bool] = Field(
        default={"explain": True, "attribution": True},
        examples=[{"explain": True, "attribution": True}],
    )


class DetectionTaskResponse(BaseModel):
    task_id: str
    status: str
    modality: str
    message: str | None = None
    is_ai_generated: bool | None = None
    confidence: float | None = None
    calibrated_confidence: float | None = None
    risk_level: str | None = None
    chunk_details: list[dict] | None = None
    explanation: dict | None = None
    arbitration_warning: str | None = None


class FeatureContribution(BaseModel):
    idiom_density: float | None = None
    punctuation_spacing: float | None = None
    ngram_entropy: float | None = None
    burstiness: float | None = None
    slop_word_density: float | None = None
    sentence_length_variance: float | None = None
    zipf_deviation: float | None = None
    punctuation_entropy: float | None = None


class SuspiciousSpan(BaseModel):
    start: int
    end: int
    reason: str
    score: float


class TextExplanation(BaseModel):
    suspicious_spans: list[SuspiciousSpan] = []
    perplexity_scores: list[dict[str, Any]] = []
    low_freq_words: list[dict[str, Any]] = []
    feature_contributions: FeatureContribution | None = None


class ImageExplanation(BaseModel):
    frequency_spectrum_url: str | None = None
    anomaly_heatmap_url: str | None = None


class PitchJumpPoint(BaseModel):
    time: float
    freq: float


class AudioExplanation(BaseModel):
    pitch_jump_points: list[PitchJumpPoint] = []
    waveform_anomaly_url: str | None = None


class ModelAttribution(BaseModel):
    model: str
    score: float


class DetectionResultResponse(BaseModel):
    task_id: str
    status: str
    modality: str
    is_ai_generated: bool | None = None
    confidence: float
    calibrated_confidence: float | None = None
    confidence_interval: tuple[float, float] | None = None
    risk_level: str | None = None
    model_attribution: list[ModelAttribution] = []
    arbitration_warning: str | None = None
    explanation: dict[str, Any] | None = None


class BatchDetectionRequest(BaseModel):
    modality: str = Field(pattern="^(text|image)$")
    options: dict[str, bool] = Field(default={"explain": True, "attribution": False})

    # 文本批量: 直接传 content_list
    content_list: list[str] | None = None


class FeedbackRequest(BaseModel):
    task_id: str
    is_correct: bool
    comment: str | None = None
