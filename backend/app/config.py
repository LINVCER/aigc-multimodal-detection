from pydantic_settings import BaseSettings
from functools import lru_cache
from dataclasses import dataclass


@dataclass
class ThresholdConfig:
    """统一阈值配置 - 集中管理所有检测阈值"""
    
    # ===== AI/人类判定阈值 =====
    TEXT_AI_THRESHOLD: float = 0.25      # 文本AI判定阈值 (RoBERTa)
    LLM_AI_THRESHOLD: float = 0.3        # LLM logprob AI判定阈值
    IMAGE_AI_THRESHOLD: float = 0.5      # 图像AI判定阈值
    AUDIO_AI_THRESHOLD: float = 0.3      # 音频AI判定阈值 (融合后)
    AUDIO_WAV2VEC_THRESHOLD: float = 0.3 # Wav2Vec2 AI判定阈值
    AUDIO_RAWNET_THRESHOLD: float = 0.5  # RawNet2 AI判定阈值
    
    # ===== 风险等级阈值 =====
    RISK_HIGH: float = 0.7               # 高风险阈值
    RISK_MEDIUM: float = 0.3             # 中风险阈值 (原0.25，统一为0.3)
    
    # ===== 论文检测阈值 =====
    THESIS_AI_THRESHOLD: float = 0.25    # 论文段落AI判定阈值
    THESIS_RISK_HIGH: float = 0.6        # 论文高风险阈值
    THESIS_RISK_MEDIUM: float = 0.3      # 论文中风险阈值
    THESIS_AI_RATE_SAFE: float = 15.0    # 论文AI率安全阈值(%)
    THESIS_AI_RATE_WARNING: float = 30.0 # 论文AI率警告阈值(%)
    
    # ===== 鲁棒性测试阈值 =====
    ROBUSTNESS_SIGNIFICANT: float = 0.15 # 攻击影响显著阈值
    ROBUSTNESS_SENSITIVE: float = 0.2    # 检测器敏感阈值
    ROBUSTNESS_STOP: float = 0.45        # 迭代改写停止阈值
    ROBUSTNESS_HIGH: float = 0.7         # 高置信度改写阈值
    ROBUSTNESS_MEDIUM: float = 0.55      # 中置信度改写阈值
    
    # ===== 风格一致性阈值 =====
    STYLE_ANOMALOUS: float = 0.15        # 风格异常一致阈值
    STYLE_CONSISTENT: float = 0.3        # 风格较一致阈值
    STYLE_NATURAL: float = 0.6           # 风格自然波动阈值
    
    # ===== 统计特征阈值 =====
    SLOP_HIGH: float = 0.8              # Slop词高频阈值
    SLOP_MEDIUM: float = 0.5            # Slop词含AI标志阈值
    TRANSITION_HIGH: float = 0.5        # 过渡词过多阈值
    TRANSITION_MEDIUM: float = 0.3      # 过渡词偏高阈值
    SENTENCE_CV_UNIFORM: float = 0.2    # 句长高度均匀阈值
    SENTENCE_CV_MODERATE: float = 0.35  # 句长较为均匀阈值
    BURSTINESS_ANOMALOUS: float = 0.15  # 节奏异常一致阈值
    BURSTINESS_UNIFORM: float = 0.25    # 节奏偏均匀阈值
    ZIPF_DEVIATION: float = 0.3         # Zipf偏差阈值
    HAPAX_LOW: float = 0.3             # Hapax比率偏低阈值
    
    @classmethod
    def get_risk_level(cls, confidence: float) -> str:
        """统一的风险等级判定"""
        if confidence >= cls.RISK_HIGH:
            return "high"
        elif confidence >= cls.RISK_MEDIUM:
            return "medium"
        return "low"
    
    @classmethod
    def get_risk_tag_type(cls, level: str) -> str:
        """风险等级对应的Element Plus标签类型"""
        return {"low": "success", "medium": "warning", "high": "danger"}.get(level, "info")


# 全局阈值配置实例
thresholds = ThresholdConfig()


class Settings(BaseSettings):
    # 应用
    app_name: str = "AIGC--多模态检测"
    debug: bool = False
    log_level: str = "INFO"

    # 数据库 MySQL
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "image_nious"
    db_user: str = "root"
    db_password: str = "root"

    @property
    def database_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""

    @property
    def celery_broker_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @property
    def celery_result_backend(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "image-nious-files"
    minio_secure: bool = False

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    # LLM API (OpenAI 兼容接口，支持 DeepSeek/Qwen/Zhipu 等)
    llm_api_key: str = ""
    llm_api_base: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"

    # Resemble AI
    resemble_ai_api_key: str = ""
    resemble_ai_monthly_limit: int = 1000

    # MiMo-VL (Anthropic-compatible API)
    mimo_api_key: str = ""
    mimo_api_base: str = "https://token-plan-cn.xiaomimimo.com/anthropic"
    mimo_model: str = "mimo-v2.5-pro"

    # 模型路径 (HuggingFace model ID, 首次使用自动下载缓存)
    model_dir: str = "../models"
    text_model_path: str = "hfl/chinese-roberta-wwm-ext"
    text_detector_checkpoint: str = "text/aigc_detector_v3_thesis.pth"
    text_detection_threshold: float = 0.25  # 最优 F1 阈值 (val set tuned)
    image_vit_model_path: str = "openai/clip-vit-large-patch14"
    image_cnn_model_path: str = "../models/image/cnn_detection.pth"
    audio_rawnet2_model_path: str = "../models/audio/rawnet2_model.pth"

    # 训练数据
    text_training_data_dir: str = "../data/training"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # 服务端口
    backend_port: int = 8001

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
