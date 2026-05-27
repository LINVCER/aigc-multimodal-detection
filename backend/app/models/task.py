import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.db.session import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        String(36), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    modality: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # text | image | audio | tampering | multimodal
    task_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="single"
    )  # single | batch
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending | processing | completed | failed
    input_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_file_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(String(36), nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user = relationship("User", back_populates="tasks")
    detection_results = relationship("DetectionResult", back_populates="task", cascade="all, delete-orphan")
