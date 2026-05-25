from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DetectionOutput:
    """统一检测器输出格式"""

    is_ai_generated: bool
    confidence: float  # 原始置信度 [0, 1]
    logit: float  # 未归一化的 logit 值（用于后续校准）
    calibrated_confidence: float | None = None
    confidence_interval: tuple[float, float] | None = None
    model_attribution: list[dict[str, Any]] = field(default_factory=list)
    explanation_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class DetectionPipeline(ABC):
    """
    检测器抽象基类 — 借鉴 UniMark 的统一 API 设计模式

    所有模态检测器必须实现: detect(), calibrate(), explain()
    """

    # 检测器标识
    name: str = "base"
    modality: str = "unknown"  # text | image | audio
    version: str = "0.1.0"

    # 校准参数（在验证集上学习）
    temperature: float = 1.0  # Temperature Scaling 参数 T
    platt_a: float = 1.0  # Platt Scaling 参数 a
    platt_b: float = 0.0  # Platt Scaling 参数 b

    @abstractmethod
    async def detect(self, input_data: Any) -> DetectionOutput:
        """执行检测，返回原始预测结果"""
        ...

    def calibrate_output(self, output: DetectionOutput) -> DetectionOutput:
        """
        对检测输出进行置信度校准（Temperature + Platt Scaling）
        子类可覆盖此方法实现自定义校准逻辑
        """
        import math

        # Temperature Scaling: p = sigmoid(logit / T)
        scaled_logit = output.logit / self.temperature
        temp_prob = 1.0 / (1.0 + math.exp(-scaled_logit))

        # Platt Scaling: p = sigmoid(a * scaled_logit + b)
        calib_logit = self.platt_a * scaled_logit + self.platt_b
        calib_prob = 1.0 / (1.0 + math.exp(-calib_logit))

        output.calibrated_confidence = round(calib_prob, 4)

        # 估计置信区间（Wilson score interval 简化版）
        n = 100  # 等效样本数
        z = 1.96  # 95% 置信度
        p = calib_prob
        margin = z * math.sqrt(p * (1 - p) / n)
        output.confidence_interval = (
            round(max(0.0, p - margin), 4),
            round(min(1.0, p + margin), 4),
        )

        return output

    @abstractmethod
    async def explain(self, input_data: Any, output: DetectionOutput) -> dict[str, Any]:
        """生成可解释性报告数据"""
        ...

    async def run(self, input_data: Any) -> DetectionOutput:
        """完整检测流程: 检测 → 校准 → 解释"""
        output = await self.detect(input_data)
        output = self.calibrate_output(output)
        output.explanation_data = await self.explain(input_data, output)
        return output
