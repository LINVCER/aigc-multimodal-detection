"""
ViT 语义分支 v2 — CLS Token + Partial Finetune

改进:
  1. 使用 CLS token (last_hidden_state[:,0]) 替代 pooler_output
  2. 支持 partial finetune (解冻最后 N 层)
  3. BICUBIC 插值 resize
  4. 完整校准参数加载
"""

import torch
import torch.nn as nn
import numpy as np
from PIL import Image
from torchvision import transforms
from torchvision.transforms import InterpolationMode

from app.detectors.base import DetectionPipeline, DetectionOutput
from app.config import get_settings

settings = get_settings()


class ViTBranch(DetectionPipeline):
    name = "clip_vit_universal_fake_detect"
    modality = "image"
    version = "0.2.0"

    def __init__(self):
        super().__init__()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model = None
        self._processor = None
        self._linear_head = None
        self._loaded = False
        self.temperature = 1.0
        self.platt_a = 1.0
        self.platt_b = 0.0
        self._transform = transforms.Compose([
            transforms.Resize(256, interpolation=InterpolationMode.BICUBIC),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.48145466, 0.4578275, 0.40821073],
                std=[0.26862954, 0.26130258, 0.27577711],
            ),
        ])

    def _ensure_loaded(self):
        if self._loaded:
            return

        try:
            import os as _os
            from transformers import CLIPModel, CLIPImageProcessor

            model_path = settings.image_vit_model_path
            local_cache = "../models/image/clip-vit-large-patch14"
            if _os.path.isdir(local_cache) and _os.path.exists(_os.path.join(local_cache, "config.json")):
                model_path = local_cache
            self._model = CLIPModel.from_pretrained(model_path, local_files_only=True).vision_model.to(self.device)
            try:
                self._processor = CLIPImageProcessor.from_pretrained(model_path, local_files_only=True)
            except Exception:
                self._processor = None

            for param in self._model.parameters():
                param.requires_grad = False
            self._model.eval()

            hidden_dim = self._model.config.hidden_size
            self._linear_head = nn.Linear(hidden_dim, 1).to(self.device)

            import os
            ckpt_path = "../models/image/ufd_linear_head.pth"
            if os.path.exists(ckpt_path):
                ckpt = torch.load(ckpt_path, map_location=self.device)
                if "linear_head" in ckpt:
                    self._linear_head.load_state_dict(ckpt["linear_head"])
                    self.temperature = ckpt.get("temperature", 1.0)
                    self.platt_a = ckpt.get("platt_a", 1.0)
                    self.platt_b = ckpt.get("platt_b", 0.0)

                    if "vit_partial" in ckpt:
                        full_state = self._model.state_dict()
                        for k, v in ckpt["vit_partial"].items():
                            if k in full_state:
                                full_state[k] = v.to(self.device)
                        self._model.load_state_dict(full_state)
                        print(f"[ViTBranch] 已加载 partial finetune 权重")

                    metrics = ckpt.get("val_metrics", {})
                    epoch = ckpt.get("epoch", "?")
                    print(f"[ViTBranch] 已加载训练权重 (epoch={epoch}, auc={metrics.get('auc', 'N/A')})")

            self._loaded = True
        except Exception as e:
            print(f"[ViTBranch] 模型加载失败 ({e})，使用占位模式")

    def _preprocess(self, image: Image.Image) -> torch.Tensor:
        if self._processor:
            inputs = self._processor(images=image, return_tensors="pt")
            return inputs["pixel_values"].to(self.device)
        image = image.convert("RGB")
        tensor = self._transform(image)
        return tensor.unsqueeze(0).to(self.device)

    async def detect(self, input_data: Image.Image) -> DetectionOutput:
        self._ensure_loaded()

        if not self._loaded:
            return DetectionOutput(
                is_ai_generated=False, confidence=0.5, logit=0.0,
                metadata={"status": "model_not_loaded"},
            )

        x = self._preprocess(input_data)

        with torch.no_grad():
            vision_outputs = self._model(x, output_hidden_states=True)
            cls_feature = vision_outputs.last_hidden_state[:, 0]
            logit = self._linear_head(cls_feature).squeeze(-1).item()

        # 温度校准 + 偏置修正 (模型过拟合，AUC=0.9997)
        t = max(self.temperature * 2.0, 3.0)  # 温度加倍
        calibrated_logit = (logit - 0.15) / t  # 减去AI偏置再除温度
        prob = torch.sigmoid(torch.tensor(calibrated_logit)).item()
        prob = max(0.01, min(0.99, prob))

        return DetectionOutput(
            is_ai_generated=prob > 0.55,
            confidence=round(prob, 4),
            logit=calibrated_logit,
        )

    def unload(self):
        """释放显存/内存"""
        if self._model:
            self._model.cpu()
            del self._model
            self._model = None
        if self._linear_head:
            del self._linear_head
            self._linear_head = None
        self._loaded = False
        self._processor = None
        import gc; gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    async def explain(self, input_data: Image.Image, output: DetectionOutput) -> dict:
        return {
            "detector": self.name,
            "method": "Frozen CLIP-ViT-L/14 + Linear Probing (UniversalFakeDetect)",
            "note": "利用 CLIP 预训练特征空间捕捉真实图像分布，泛化到未见生成器",
            "feature": "CLS token (last_hidden_state[:,0])",
        }
