"""
差异报告器 — 记录降 AIGC 过程中每一步的变化

数据结构:
  - ChangeRecord: 单条变更记录
  - ReduceStep: 单步处理结果 (含检测分数、回滚信息)
  - ReduceReport: 完整优化报告
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ChangeRecord:
    """一条具体的文本变更"""
    category: str       # "slop_removed" | "transition_replaced" | "sentence_split" |
                        # "sentence_merged" | "rhythm_injected" | "repetition_reduced" |
                        # "process_added" | "aside_added" | "hedging_applied" |
                        # "llm_rewritten" | "rollback"
    description: str    # 人类可读的描述
    count: int = 1      # 变更数量


@dataclass
class FeatureSnapshot:
    """某一时刻的特征快照"""
    ai_confidence: float
    features: dict[str, float] = field(default_factory=dict)

    def delta(self, other: FeatureSnapshot) -> float:
        return round(self.ai_confidence - other.ai_confidence, 4)


@dataclass
class ReduceStep:
    """单步优化记录"""
    step_name: str                # "结构扰动" | "局部人类化" | "LLM改写-轮1" 等
    before: FeatureSnapshot
    after: FeatureSnapshot
    changes: list[ChangeRecord] = field(default_factory=list)
    rolled_back: bool = False     # 是否因 AI 率升高而回滚
    error: str | None = None

    @property
    def delta(self) -> float:
        return self.after.delta(self.before)

    @property
    def improved(self) -> bool:
        return self.after.ai_confidence < self.before.ai_confidence


@dataclass
class ReduceReport:
    """完整优化报告"""
    original_text: str
    optimized_text: str
    original_snapshot: FeatureSnapshot
    final_snapshot: FeatureSnapshot
    steps: list[ReduceStep] = field(default_factory=list)
    feature_gaps: list[dict] = field(default_factory=list)  # FeatureGap 的 dict 形式
    generated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    @property
    def original_confidence(self) -> float:
        return self.original_snapshot.ai_confidence

    @property
    def final_confidence(self) -> float:
        return self.final_snapshot.ai_confidence

    @property
    def reduction_rate(self) -> float:
        orig = self.original_confidence
        if orig < 0.01:
            return 0.0
        return round(max(0, orig - self.final_confidence) / orig * 100, 1)

    @property
    def verdict(self) -> str:
        fc = self.final_confidence
        rr = self.reduction_rate
        if fc < 0.3 and rr > 5:
            return f"优化成功：AI置信度降至{fc:.0%}，通过检测阈值（<30%）"
        elif fc < 0.3 and rr <= 0:
            return f"文本已是人类风格（AI率{fc:.0%}），无需优化"
        elif rr > 30:
            return f"大幅降低{rr:.0f}%，但AI率仍偏高（{fc:.0%}），建议进一步人工改写"
        elif rr > 15:
            return f"降低了{rr:.0f}%，需继续优化以达到安全阈值"
        elif rr > 0:
            return f"小幅降低{rr:.0f}%，当前文本AI痕迹较重，建议重写核心段落"
        else:
            return "未能有效降低AI率，建议重新构思内容或人工改写核心段落"

    def to_dict(self) -> dict:
        """转换为 API 可序列化的 dict"""
        return {
            "original_confidence": self.original_confidence,
            "final_confidence": self.final_confidence,
            "reduction_rate": self.reduction_rate,
            "verdict": self.verdict,
            "original_text": self.original_text,
            "optimized_text": self.optimized_text,
            "feature_gaps": self.feature_gaps,
            "steps": [
                {
                    "step_name": s.step_name,
                    "before_confidence": s.before.ai_confidence,
                    "after_confidence": s.after.ai_confidence,
                    "delta": s.delta,
                    "improved": s.improved,
                    "rolled_back": s.rolled_back,
                    "error": s.error,
                    "changes": [
                        {"category": c.category, "description": c.description, "count": c.count}
                        for c in s.changes
                    ],
                }
                for s in self.steps
            ],
            "generated_at": self.generated_at,
        }

    def to_text_report(self) -> str:
        """生成纯文本报表"""
        lines = []
        lines.append("=" * 60)
        lines.append("AIGC检测 论文 AIGC 优化报告")
        lines.append("=" * 60)
        lines.append(f"生成时间: {self.generated_at}")
        lines.append("")
        lines.append("-" * 60)
        lines.append("检测结果对比")
        lines.append("-" * 60)
        lines.append(f"优化前 AI 率: {self.original_confidence:.1%}")
        lines.append(f"优化后 AI 率: {self.final_confidence:.1%}")
        lines.append(f"降低幅度:   {self.reduction_rate:.1f}%")
        lines.append(f"判定结果:   {self.verdict}")
        lines.append("")

        if self.feature_gaps:
            lines.append("-" * 60)
            lines.append("特征差距分析 (Top 5)")
            lines.append("-" * 60)
            for gap in self.feature_gaps[:5]:
                lines.append(
                    f"  {gap['feature_name']:30s} "
                    f"值={gap['current_value']:.4f}  "
                    f"AI贡献={gap['ai_contribution']:.2%}  "
                    f"权重={gap['weight']:.2f}"
                )
                if gap.get("suggestion"):
                    lines.append(f"    → {gap['suggestion']}")
            lines.append("")

        lines.append("-" * 60)
        lines.append("优化步骤日志")
        lines.append("-" * 60)
        for i, s in enumerate(self.steps):
            prefix = "  [已回滚]" if s.rolled_back else ""
            if s.error:
                lines.append(f"  Step {i+1}: {s.step_name} — 失败 ({s.error})")
            else:
                lines.append(
                    f"  Step {i+1}: {s.step_name}{prefix} — "
                    f"AI率 {s.before.ai_confidence:.1%} → {s.after.ai_confidence:.1%} "
                    f"(Δ={s.delta:+.1%})"
                )
                for c in s.changes:
                    lines.append(f"    · {c.description}")
        lines.append("")

        lines.append("-" * 60)
        lines.append("优化后文本")
        lines.append("-" * 60)
        lines.append(self.optimized_text)
        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)
