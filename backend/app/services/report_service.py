import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.report import ExplanationReport
from app.models.detection import DetectionResult


async def create_report(
    db: AsyncSession,
    detection_result_id: str,
    modality: str,
    suspicious_spans: dict | None = None,
    perplexity_scores: dict | None = None,
    low_freq_words: dict | None = None,
    feature_contributions: dict | None = None,
    frequency_spectrum_url: str | None = None,
    anomaly_heatmap_url: str | None = None,
    pitch_jump_points: dict | None = None,
    waveform_anomaly_url: str | None = None,
    arbitration_reason: str | None = None,
    conflicting_signals: dict | None = None,
) -> ExplanationReport:
    report = ExplanationReport(
        id=uuid.uuid4(),
        detection_result_id=detection_result_id,
        modality=modality,
        suspicious_spans=suspicious_spans,
        perplexity_scores=perplexity_scores,
        low_freq_words=low_freq_words,
        feature_contributions=feature_contributions,
        frequency_spectrum_url=frequency_spectrum_url,
        anomaly_heatmap_url=anomaly_heatmap_url,
        pitch_jump_points=pitch_jump_points,
        waveform_anomaly_url=waveform_anomaly_url,
        arbitration_reason=arbitration_reason,
        conflicting_signals=conflicting_signals,
    )
    db.add(report)
    await db.flush()
    await db.refresh(report)
    return report


async def get_report(db: AsyncSession, detection_result_id: str) -> ExplanationReport | None:
    result = await db.execute(
        select(ExplanationReport).where(
            ExplanationReport.detection_result_id == detection_result_id
        )
    )
    return result.scalar_one_or_none()
