"""
Chinese-RoBERTa 检测器 — 借鉴 AIGC_text_detector 的深度学习分支

使用哈工大 Chinese-RoBERTa-wwm-ext 作为基座，在 HC3-Chinese 上微调 (或使用预训练权重)
输出原始 logit 和概率，供后续校准和融合使用
"""

import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModel

from app.detectors.base import DetectionPipeline, DetectionOutput
from app.config import get_settings

settings = get_settings()


class ChineseRobertaDetector(DetectionPipeline):
    name = "chinese_roberta_wwm_ext"
    modality = "text"
    version = "0.1.0"

    def __init__(self):
        super().__init__()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model = None
        self._tokenizer = None
        self._classifier = None
        self._loaded = False

    def _ensure_loaded(self):
        """延迟加载模型，避免启动时占用大量内存"""
        if self._loaded:
            return

        model_path = settings.text_model_path
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
            self._model = AutoModel.from_pretrained(model_path, trust_remote_code=True).to(self.device)
            self._model.eval()
            # 分类头 (需与训练脚本结构一致)
            hidden_size = self._model.config.hidden_size
            self._classifier = nn.Sequential(
                nn.Dropout(0.1),
                nn.Linear(hidden_size, 256),
                nn.ReLU(),
                nn.Dropout(0.1),
                nn.Linear(256, 1),
            ).to(self.device)
            self._loaded = True
            # 加载训练好的分类头权重
            import os
            ckpt_name = getattr(settings, "text_detector_checkpoint", "text/aigc_detector.pth")
            ckpt_paths = [
                os.path.join(settings.model_dir, ckpt_name),
                os.path.join(os.path.dirname(model_path), "aigc_detector.pth"),
                "../models/text/aigc_detector.pth",
            ]
            ckpt_path = None
            for p in ckpt_paths:
                if os.path.exists(p):
                    ckpt_path = p
                    break
            if ckpt_path:
                ckpt = torch.load(ckpt_path, map_location=self.device)
                if "classifier_state_dict" in ckpt:
                    # 训练时用 2 类输出，推理转为单 logit
                    sd = ckpt["classifier_state_dict"]
                    if sd["4.weight"].shape[0] == 2:
                        w = sd["4.weight"].data
                        b = sd["4.bias"].data
                        sd["4.weight"] = (w[1:2] - w[0:1])
                        sd["4.bias"] = (b[1:2] - b[0:1])
                    self._classifier.load_state_dict(sd)
                    self.temperature = ckpt.get("temperature", 1.0)
                    self.platt_a = ckpt.get("platt_a", 1.0)
                    self.platt_b = ckpt.get("platt_b", 0.0)
                    print(f"[RobertaDetector] 已加载训练权重 "
                          f"(Val Acc={ckpt.get('val_acc','N/A')}, F1={ckpt.get('val_f1','N/A')}, "
                          f"T={self.temperature:.3f}, Platt=({self.platt_a:.3f},{self.platt_b:.3f}))")
        except Exception as e:
            print(f"[RobertaDetector] 模型加载失败 ({e})，使用随机权重占位模式")

    def _encode(self, text: str) -> torch.Tensor:
        """编码文本获取 [CLS] embedding"""
        inputs = self._tokenizer(
            text,
            max_length=512,
            padding=True,
            truncation=True,
            return_tensors="pt",
        ).to(self.device)

        with torch.no_grad():
            outputs = self._model(**inputs)
            cls_embedding = outputs.last_hidden_state[:, 0, :]  # [CLS]
        return cls_embedding

    async def detect(self, input_data: str) -> DetectionOutput:
        import asyncio

        try:
            self._ensure_loaded()
        except Exception:
            return DetectionOutput(
                is_ai_generated=False,
                confidence=0.5,
                logit=0.0,
                metadata={"status": "model_load_error"},
            )

        if not self._loaded:
            return DetectionOutput(
                is_ai_generated=False,
                confidence=0.5,
                logit=0.0,
                metadata={"status": "model_not_loaded", "note": "请下载 Chinese-RoBERTa-wwm-ext 模型权重"},
            )

        try:
            embedding = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, self._encode, input_data),
                timeout=15,
            )
        except (asyncio.TimeoutError, Exception):
            return DetectionOutput(
                is_ai_generated=False,
                confidence=0.5,
                logit=0.0,
                metadata={"status": "model_inference_timeout"},
            )

        logit = self._classifier(embedding).squeeze(-1).item()

        # 应用训练时学到的校准参数
        T = getattr(self, "temperature", 1.0)
        a = getattr(self, "platt_a", 1.0)
        b = getattr(self, "platt_b", 0.0)
        scaled_logit = logit / max(T, 0.1)
        calibrated_logit = a * scaled_logit + b
        prob = torch.sigmoid(torch.tensor(calibrated_logit)).item()

        return DetectionOutput(
            is_ai_generated=prob > 0.25,
            confidence=round(prob, 4),
            logit=calibrated_logit,
        )

    async def explain(self, input_data: str, output: DetectionOutput) -> dict:
        return {
            "detector": self.name,
            "method": "Chinese-RoBERTa-wwm-ext [CLS] embedding + Linear head",
            "note": "深度语义特征分析，关注全局写作风格异常",
        }
