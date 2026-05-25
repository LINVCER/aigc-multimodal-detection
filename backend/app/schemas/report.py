from pydantic import BaseModel


class ReportResponse(BaseModel):
    id: str
    detection_result_id: str
    modality: str
    suspicious_spans: list[dict] | None = None
    perplexity_scores: list[dict] | None = None
    low_freq_words: list[dict] | None = None
    feature_contributions: dict | None = None
    frequency_spectrum_url: str | None = None
    anomaly_heatmap_url: str | None = None
    pitch_jump_points: list[dict] | None = None
    waveform_anomaly_url: str | None = None
    arbitration_reason: str | None = None
    conflicting_signals: dict | None = None

    model_config = {"from_attributes": True}


class HistoryItem(BaseModel):
    task_id: str
    modality: str
    status: str
    is_ai_generated: bool | None = None
    confidence: float
    risk_level: str | None = None
    created_at: str
    input_content: str | None = None


class HistoryResponse(BaseModel):
    items: list[HistoryItem]
    total: int
    page: int
    size: int
