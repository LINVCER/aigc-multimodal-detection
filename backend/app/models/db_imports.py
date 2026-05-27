# 确保所有模型被 Base.metadata 注册
from app.models.user import User
from app.models.task import Task
from app.models.detection import DetectionResult
from app.models.report import ExplanationReport

__all__ = ["User", "Task", "DetectionResult", "ExplanationReport"]
