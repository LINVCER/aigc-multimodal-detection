"""
风险等级判定服务 - 统一的风险等级判定逻辑
"""

from app.config import thresholds


class RiskService:
    """风险等级判定服务"""

    @staticmethod
    def get_risk_level(confidence: float) -> str:
        """
        根据置信度返回风险等级
        
        Args:
            confidence: 置信度 (0-1)
            
        Returns:
            风险等级: 'low', 'medium', 'high'
        """
        return thresholds.get_risk_level(confidence)

    @staticmethod
    def get_risk_tag_type(level: str) -> str:
        """
        根据风险等级返回Element Plus标签类型
        
        Args:
            level: 风险等级
            
        Returns:
            Element Plus类型: 'success', 'warning', 'danger', 'info'
        """
        return thresholds.get_risk_tag_type(level)

    @staticmethod
    def get_risk_text(level: str) -> str:
        """
        根据风险等级返回中文文本
        
        Args:
            level: 风险等级
            
        Returns:
            中文文本
        """
        mapping = {
            "low": "低风险",
            "medium": "中风险",
            "high": "高风险",
        }
        return mapping.get(level, "未知")

    @staticmethod
    def get_risk_color(level: str) -> str:
        """
        根据风险等级返回颜色
        
        Args:
            level: 风险等级
            
        Returns:
            颜色值
        """
        mapping = {
            "low": "#10b981",
            "medium": "#f59e0b",
            "high": "#dc2626",
        }
        return mapping.get(level, "#6b7280")

    @staticmethod
    def get_thesis_risk_level(ai_rate: float) -> str:
        """
        根据论文AI率返回风险等级
        
        Args:
            ai_rate: AI率 (百分比)
            
        Returns:
            风险等级: 'low', 'medium', 'high'
        """
        if ai_rate > thresholds.THESIS_AI_RATE_WARNING:
            return "high"
        elif ai_rate > thresholds.THESIS_AI_RATE_SAFE:
            return "medium"
        return "low"

    @staticmethod
    def get_thesis_suggestion(ai_rate: float) -> str:
        """
        根据论文AI率返回建议
        
        Args:
            ai_rate: AI率 (百分比)
            
        Returns:
            建议文本
        """
        if ai_rate <= thresholds.THESIS_AI_RATE_SAFE:
            return "通过"
        elif ai_rate <= thresholds.THESIS_AI_RATE_WARNING:
            return "需修改"
        return "不通过"


# 全局风险服务实例
risk_service = RiskService()
