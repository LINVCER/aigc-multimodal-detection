"""Mask R-CNN 篡改检测分支 — 长边缩放 + TTA + 多尺度推理"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

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

# 长边缩放目标尺寸 (保持纵横比)
TARGET_SIZES = [800, 1000, 1200]

# 双阈值策略
SCORE_THRESHOLD_LOW = 0.3
SCORE_THRESHOLD_HIGH = 0.6
MASK_THRESHOLD_HIGH = 0.6
MASK_THRESHOLD_LOW = 0.4
CONFIDENCE_FILTER_THRESHOLD = 0.45


class MaskRCNNBranch(SpatialEvidenceBranch):
    name = "maskrcnn_resnet50_fpn"
    version = "1.0.0"

    def __init__(self, checkpoint_path: str | None = None):
        self._model = None
        self._device: torch.device | None = None
        self._checkpoint_path = checkpoint_path
        self._loaded = False
        self._transform = T.Compose([
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def _default_checkpoint_path(self) -> str:
        from app.config import get_settings
        return get_settings().tampering_maskrcnn_checkpoint

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        ckpt = self._checkpoint_path or self._default_checkpoint_path()
        if not Path(ckpt).exists():
            logger.warning("Tampering checkpoint not found: %s", ckpt)
            return
        try:
            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            model = maskrcnn_resnet50_fpn(pretrained=False)
            num_classes = 2
            in_features = model.roi_heads.box_predictor.cls_score.in_features
            model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)
            in_features_mask = model.roi_heads.mask_predictor.conv5_mask.in_channels
            model.roi_heads.mask_predictor = MaskRCNNPredictor(in_features_mask, 256, num_classes)
            checkpoint = torch.load(ckpt, map_location=self._device, weights_only=False)
            if "model_state_dict" in checkpoint:
                model.load_state_dict(checkpoint["model_state_dict"])
            else:
                model.load_state_dict(checkpoint)
            model.to(self._device)
            model.eval()
            self._model = model
            self._loaded = True
            logger.info("Tampering Mask R-CNN loaded on %s", self._device)
        except Exception:
            logger.exception("Failed to load tampering model")

    def _resize_long_edge(self, image: Image.Image, target: int) -> Image.Image:
        """长边缩放到 target，保持纵横比"""
        w, h = image.size
        if max(w, h) <= target:
            return image
        scale = target / max(w, h)
        return image.resize((int(w * scale), int(h * scale)), Image.BICUBIC)

    async def detect(self, image: Image.Image) -> BranchResult:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._detect_sync, image)

    def _detect_sync(self, image: Image.Image) -> BranchResult:
        self._ensure_loaded()
        if not self._loaded:
            h, w = image.height, image.width
            return BranchResult(
                branch_name=self.name,
                score_map=np.zeros((h, w), dtype=np.float32),
                confidence=0.0,
                mask=np.zeros((h, w), dtype=bool),
                metadata={"status": "model_not_loaded"},
            )

        w, h = image.width, image.height
        final_mask = np.zeros((h, w), dtype=np.uint8)
        final_score_map = np.zeros((h, w), dtype=np.float32)
        instance_scores: list[float] = []

        for target_size in TARGET_SIZES:
            resized = self._resize_long_edge(image, target_size)
            rw, rh = resized.size
            # 原图推理 + 水平翻转推理 (TTA)
            for flip in [False, True]:
                if flip:
                    pil_img = resized.transpose(Image.FLIP_LEFT_RIGHT)
                else:
                    pil_img = resized
                img_tensor = self._transform(pil_img).unsqueeze(0).to(self._device)
                with torch.no_grad():
                    pred = self._model(img_tensor)[0]
                masks = pred["masks"].cpu().numpy()
                scores = pred["scores"].cpu().numpy()
                for m, score in zip(masks, scores):
                    if score < SCORE_THRESHOLD_LOW:
                        continue
                    instance_scores.append(float(score))
                    if score > SCORE_THRESHOLD_HIGH:
                        binary = (m[0] > MASK_THRESHOLD_HIGH).astype(np.uint8)
                    else:
                        binary = (m[0] > MASK_THRESHOLD_LOW).astype(np.uint8)
                    if flip:
                        binary = np.fliplr(binary).copy()
                    # 缩放回原图尺寸 (INTER_NEAREST 避免灰色过渡带)
                    if (rw, rh) != (w, h):
                        binary = cv2.resize(binary, (w, h), interpolation=cv2.INTER_NEAREST)
                    final_mask = cv2.bitwise_or(final_mask, binary)
                    final_score_map = np.maximum(final_score_map, binary * float(score))

        # 置信度过滤
        filtered_mask = (final_mask > 0) & (final_score_map > CONFIDENCE_FILTER_THRESHOLD)
        global_prob = float(np.max(instance_scores)) if instance_scores else 0.0

        return BranchResult(
            branch_name=self.name,
            score_map=final_score_map,
            confidence=round(global_prob, 4),
            mask=filtered_mask,
            metadata={"scales": TARGET_SIZES, "tta": True, "device": str(self._device),
                       "instance_scores": instance_scores},
        )
