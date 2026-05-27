import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.db.session import Base


class ExplanationReport(Base):
    __tablename__ = "explanation_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        String(36), primary_key=True, default=uuid.uuid4
    )
    detection_result_id: Mapped[uuid.UUID] = mapped_column(
        String(36), ForeignKey("detection_results.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    modality: Mapped[str] = mapped_column(String(20), nullable=False)

    # 文本检测解释
    suspicious_spans: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    perplexity_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    low_freq_words: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    feature_contributions: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # 图像检测解释
    frequency_spectrum_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    anomaly_heatmap_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # 音频检测解释
    pitch_jump_points: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    waveform_anomaly_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # 仲裁层解释
    arbitration_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflicting_signals: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    detection_result = relationship("DetectionResult", back_populates="explanation_report")
