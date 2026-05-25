"""
标识检测 API — GB 45438—2025 + C2PA 双标准支持
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/identify", tags=["标识检测"])


@router.post("/image")
async def identify_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    图像标识检测 — C2PA + GB 45438 双标准

    检查图像是否包含:
      1. C2PA Content Credentials 数字签名
      2. GB 45438—2025 合规元数据标识
    返回双通道检测结果
    """
    from app.detectors.metadata.c2pa_detector import check_c2pa
    from app.detectors.metadata.gb45438_detector import check_gb45438_image
    from app.services.image_service import detect_image as detect_ai

    image_data = await file.read()

    # 通道1: C2PA 标识检测
    c2pa_result = check_c2pa(image_data, file.filename or "")

    # 通道2: GB 45438 标识检测
    gb_result = check_gb45438_image(image_data)

    # 通道3: 内容识别 (AI 检测)
    ai_result = await detect_ai(image_data, {"explain": False})

    return {
        "filename": file.filename,
        # 标识检测
        "identifier_detection": {
            "c2pa": {
                "detected": c2pa_result.detected,
                "manifest_count": c2pa_result.manifest_count,
                "issuer": c2pa_result.issuer,
                "generator": c2pa_result.generator,
                "signature_valid": c2pa_result.signature_valid,
                "details": c2pa_result.details,
            },
            "gb45438": {
                "detected": gb_result.detected,
                "has_explicit_mark": gb_result.has_explicit_mark,
                "has_implicit_mark": gb_result.has_implicit_mark,
                "compliance_level": gb_result.compliance_level,
                "generator": gb_result.generator,
                "details": gb_result.details,
            },
        },
        # 内容识别
        "content_detection": {
            "is_ai_generated": ai_result.is_ai_generated,
            "confidence": ai_result.confidence,
        },
        # 综合判定
        "verdict": _arbitrate(ai_result.is_ai_generated, ai_result.confidence,
                              c2pa_result.detected, gb_result.detected),
    }


@router.post("/text")
async def identify_text(
    content: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    """文本标识检测 — GB 45438 显式标识"""
    from app.detectors.metadata.gb45438_detector import check_gb45438_text
    from app.services.text_service import detect_text as detect_ai

    gb_result = check_gb45438_text(content)
    ai_result = await detect_ai(content, {"explain": False})

    return {
        "gb45438": {
            "detected": gb_result.detected,
            "has_explicit_mark": gb_result.has_explicit_mark,
            "compliance_level": gb_result.compliance_level,
            "details": gb_result.details,
        },
        "content_detection": {
            "is_ai_generated": ai_result.is_ai_generated,
            "confidence": ai_result.confidence,
        },
        "verdict": _arbitrate_text(ai_result.is_ai_generated, ai_result.confidence,
                                    gb_result.detected),
    }


def _arbitrate(is_ai: bool, conf: float, c2pa: bool, gb: bool) -> dict:
    """双通道综合判定"""
    identifier_found = c2pa or gb

    if identifier_found:
        if conf > 0.5:
            level = "confirmed"
            msg = "标识检测确认该内容为 AI 生成，且内容分析也支持此判定"
        else:
            level = "identifier_only"
            msg = "检测到 AI 标识元数据，但内容分析未发现明显 AI 特征 (可能经过后期编辑)"
    else:
        if conf > 0.8:
            level = "content_detected"
            msg = "未检测到 AI 标识，但内容分析高度疑似 AI 生成 (建议添加合规标识)"
        elif conf > 0.5:
            level = "suspected"
            msg = "未检测到 AI 标识，内容分析显示部分 AI 特征"
        else:
            level = "clean"
            msg = "未检测到 AI 标识，内容分析也未发现 AI 特征"

    return {"level": level, "message": msg}


def _arbitrate_text(is_ai: bool, conf: float, gb: bool) -> dict:
    return _arbitrate(is_ai, conf, False, gb)
