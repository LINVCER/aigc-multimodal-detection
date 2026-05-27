import uuid
from datetime import datetime
from sqlalchemy import String, Text, Float, Boolean, DateTime, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.db.session import Base


class DetectionResult(Base):
    __tablename__ = "detection_results"

    id: Mapped[uuid.UUID] = mapped_column(
        String(36), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    modality: Mapped[str] = mapped_column(String(20), nullable=False)
    is_ai_generated: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    calibrated_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_interval_lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_interval_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(10), nullable=True)  # low | medium | high
    raw_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_attribution: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    arbitration_warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    task = relationship("Task", back_populates="detection_results")
    explanation_report = relationship(
        "ExplanationReport", back_populates="detection_result",
        uselist=False, cascade="all, delete-orphan"
    )
