"""空间证据分支抽象基类"""

from __future__ import annotations

from abc import ABC, abstractmethod

from PIL import Image

from app.detectors.tampering.output import BranchResult


class SpatialEvidenceBranch(ABC):
    """所有篡改检测分支的基类，统一 predict(image) -> BranchResult 接口"""

    name: str = "base"
    modality: str = "image_tampering"
    version: str = "0.0.0"

    @abstractmethod
    async def detect(self, image: Image.Image) -> BranchResult:
        """对输入图像执行检测，返回 BranchResult"""
        ...
