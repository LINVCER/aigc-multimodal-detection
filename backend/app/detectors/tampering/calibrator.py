"""篡改置信度校准 — tampering_score 加权公式"""

from __future__ import annotations

import numpy as np

from app.detectors.tampering.output import BranchResult


def _compute_iou(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    intersection = np.logical_and(mask_a, mask_b).sum()
    union = np.logical_or(mask_a, mask_b).sum()
    if union == 0:
        return 0.0
    return float(intersection / union)


def _mask_area_score(area_ratio: float, area_cap: float = 0.15) -> float:
    """分段面积得分: <5% 线性, 5%-30% 缓增, >30% 对数衰减"""
    if area_ratio < 0.05:
        return min(area_ratio / area_cap, 1.0)
    elif area_ratio < 0.30:
        # 缓增: 5%→0.33, 30%→0.7
        return 0.33 + (area_ratio - 0.05) * (0.37 / 0.25)
    else:
        # 对数衰减，避免大面积 retouching 虚高
        return min(0.7 + 0.3 * np.log1p(area_ratio - 0.30) / np.log1p(1.0), 1.0)


def _classify_tampering_type(mask: np.ndarray, branch_results: list[BranchResult]) -> str:
    """启发式篡改类型判定"""
    if not mask.any():
        return "unknown"
    area_ratio = mask.sum() / mask.size
    if area_ratio > 0.3:
        return "retouching"
    elif area_ratio < 0.01:
        return "copy_move"
    else:
        return "splicing"


class TamperingCalibrator:
    """计算最终 tampering_score 和篡改类型"""

    def __init__(
        self,
        weight_area: float = 0.55,
        weight_confidence: float = 0.30,
        weight_consistency: float = 0.15,
        exif_weight: float = 0.10,
    ):
        self.weight_area = weight_area
        self.weight_confidence = weight_confidence
        self.weight_consistency = weight_consistency
        self.exif_weight = exif_weight

    def compute(
        self,
        mask: np.ndarray,
        dl_result: BranchResult,
        branch_results: list[BranchResult],
    ) -> tuple[float, str]:
        """返回 (tampering_score, tampering_type)"""
        # 1. mask_area_score (分段函数)
        area_ratio = mask.sum() / mask.size
        area_score = _mask_area_score(area_ratio)

        # 2. confidence_score: DL top-k 实例分数均值
        instance_scores = dl_result.metadata.get("instance_scores", [dl_result.confidence])
        if instance_scores:
            top_k = sorted(instance_scores, reverse=True)[:5]
            confidence_score = float(np.mean(top_k))
        else:
            confidence_score = dl_result.confidence

        # 3. branch_consistency: DL mask 与其他分支 score_map 阈值化后的 IoU
        ious = []
        for br in branch_results:
            if br.branch_name == dl_result.branch_name:
                continue
            if br.mask is not None:
                ious.append(_compute_iou(mask, br.mask))
            else:
                binary = br.score_map > 0.5
                ious.append(_compute_iou(mask, binary))
        consistency_score = float(np.mean(ious)) if ious else 0.5

        # 4. EXIF 修正: 高 EXIF 置信度提升总分
        exif_confidence = 0.0
        for br in branch_results:
            if br.branch_name == "exif_metadata":
                exif_confidence = br.confidence
                break

        # 加权计算
        base_score = (
            self.weight_area * area_score
            + self.weight_confidence * confidence_score
            + self.weight_consistency * consistency_score
        )
        # EXIF 修正 (加性)
        tampering_score = min(base_score + self.exif_weight * exif_confidence, 1.0)

        # 篡改类型
        tampering_type = _classify_tampering_type(mask, branch_results)

        return round(tampering_score, 4), tampering_type
