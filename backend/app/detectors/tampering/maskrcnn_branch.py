"""
Mask R-CNN 深度学习分支 — 匹配原始项目的 multi_scale_pipeline

2 尺度推理 + 双阈值二值化 + 置信度过滤
"""

import asyncio
import logging

import cv2
import numpy as np
import torch
from PIL import Image
from torchvision import transforms as T
from torchvision.models.detection import maskrcnn_resnet50_fpn
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from torchvision.models.detection.mask_rcnn import MaskRCNNPredictor

from app.detectors.tampering.base import SpatialEvidenceBranch
from app.detectors.tampering.output import BranchResult

logger = logging.getLogger(__name__)

SCORE_THRESHOLD_LOW = 0.3
SCORE_THRESHOLD_HIGH = 0.6
MASK_THRESHOLD_LOW = 0.4
MASK_THRESHOLD_HIGH = 0.6
CONFIDENCE_FILTER = 0.45


class MaskRCNNBranch(SpatialEvidenceBranch):
    name = "maskrcnn_resnet50_fpn"
    version = "1.0.0"

    def __init__(self, checkpoint_path: str | None = None):
        self._model = None
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._checkpoint_path = checkpoint_path
        self._loaded = False
        self._transform = T.Compose([
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        try:
            from app.config import get_settings
            ckpt = self._checkpoint_path or get_settings().tampering_maskrcnn_checkpoint
            model = maskrcnn_resnet50_fpn(pretrained=False)
            num_classes = 2
            in_features = model.roi_heads.box_predictor.cls_score.in_features
            model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)
            in_features_mask = model.roi_heads.mask_predictor.conv5_mask.in_channels
            model.roi_heads.mask_predictor = MaskRCNNPredictor(in_features_mask, 256, num_classes)
            state = torch.load(ckpt, map_location=self._device, weights_only=False)
            if "model_state_dict" in state:
                state = state["model_state_dict"]
            model.load_state_dict(state)
            model.to(self._device)
            model.eval()
            self._model = model
            self._loaded = True
            logger.info("Mask R-CNN loaded on %s", self._device)
        except Exception:
            logger.exception("Failed to load tampering model")

    async def detect(self, image: Image.Image) -> BranchResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._detect_sync, image)

    def _detect_sync(self, image: Image.Image) -> BranchResult:
        self._ensure_loaded()
        if not self._loaded:
            h, w = image.height, image.width
            return BranchResult(
                branch_name=self.name, score_map=np.zeros((h, w), dtype=np.float32),
                confidence=0.0, mask=np.zeros((h, w), dtype=bool),
                metadata={"status": "model_not_loaded"},
            )

        w, h = image.size
        final_mask = np.zeros((h, w), dtype=np.uint8)
        final_score_map = np.zeros((h, w), dtype=np.float32)
        instance_scores: list[float] = []

        scales = [1.0, 0.75]
        for s in scales:
            new_w, new_h = int(w * s), int(h * s)
            resized = image.resize((new_w, new_h))
            img_tensor = self._transform(resized).unsqueeze(0).to(self._device)

            with torch.no_grad():
                pred = self._model(img_tensor)[0]

            masks = pred["masks"].cpu().numpy()
            scores = pred["scores"].cpu().numpy()

            for m, score in zip(masks, scores):
                if score < SCORE_THRESHOLD_LOW:
                    continue
                if score > SCORE_THRESHOLD_HIGH:
                    binary = (m[0] > MASK_THRESHOLD_HIGH).astype(np.uint8)
                else:
                    binary = (m[0] > MASK_THRESHOLD_LOW).astype(np.uint8)

                if s != 1.0:
                    binary = cv2.resize(binary, (w, h), interpolation=cv2.INTER_NEAREST)

                final_mask = cv2.bitwise_or(final_mask, binary)
                score_float = float(score)
                final_score_map = np.maximum(final_score_map, binary * score_float)
                instance_scores.append(score_float)

        # 置信度过滤: 保留 score_map > 0.45 的区域
        filtered_mask = (final_mask > 0) & (final_score_map > CONFIDENCE_FILTER)

        return BranchResult(
            branch_name=self.name,
            score_map=final_score_map,
            confidence=round(float(np.mean(instance_scores)), 4) if instance_scores else 0.0,
            mask=filtered_mask,
            metadata={"instance_scores": instance_scores},
        )
