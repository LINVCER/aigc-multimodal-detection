"""
Admin API endpoints - data analytics, model optimization, user detection content statistics
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_, case
from datetime import datetime, timedelta

from app.api.deps import get_db, get_current_admin
from app.models.user import User
from app.models.task import Task
from app.models.detection import DetectionResult
from app.models.report import ExplanationReport
from app.services.calibration import _calibrator

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Get platform core statistics"""
    total_users_result = await db.execute(select(func.count(User.id)))
    total_users = total_users_result.scalar()

    total_tasks_result = await db.execute(select(func.count(Task.id)))
    total_tasks = total_tasks_result.scalar()

    completed_tasks_result = await db.execute(
        select(func.count(Task.id)).where(Task.status == "completed")
    )
    completed_tasks = completed_tasks_result.scalar()

    ai_detected_result = await db.execute(
        select(func.count(DetectionResult.id)).where(
            DetectionResult.is_ai_generated == True
        )
    )
    ai_detected = ai_detected_result.scalar()

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_tasks_result = await db.execute(
        select(func.count(Task.id)).where(Task.created_at >= today)
    )
    today_tasks = today_tasks_result.scalar()

    return {
        "total_users": total_users,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "ai_detected_count": ai_detected,
        "detection_rate": round(ai_detected / max(completed_tasks, 1), 4),
        "today_tasks": today_tasks,
    }


@router.get("/trend")
async def get_trend(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Get detection trend data (daily statistics)"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    from sqlalchemy import cast, Date

    daily_stats = await db.execute(
        select(
            cast(Task.created_at, Date).label("date"),
            func.count(Task.id).label("total"),
            func.sum(case((Task.status == "completed", 1), else_=0)).label("completed"),
            func.sum(case((Task.status == "failed", 1), else_=0)).label("failed"),
        )
        .where(Task.created_at >= start_date)
        .group_by(cast(Task.created_at, Date))
        .order_by("date")
    )

    trend_data = []
    for row in daily_stats.all():
        trend_data.append({
            "date": row.date.strftime("%m-%d") if row.date else "",
            "total": row.total or 0,
            "completed": int(row.completed or 0),
            "failed": int(row.failed or 0),
        })

    modality_stats = await db.execute(
        select(
            DetectionResult.modality,
            func.count(DetectionResult.id).label("count"),
            func.avg(DetectionResult.confidence).label("avg_confidence"),
            func.sum(case((DetectionResult.is_ai_generated == True, 1), else_=0)).label("ai_count"),
        )
        .where(DetectionResult.created_at >= start_date)
        .group_by(DetectionResult.modality)
    )

    modality_data = []
    for row in modality_stats.all():
        total = row.count or 0
        ai_count = int(row.ai_count or 0)
        modality_data.append({
            "modality": row.modality,
            "count": total,
            "ai_count": ai_count,
            "human_count": total - ai_count,
            "ai_rate": round(ai_count / max(total, 1), 4),
            "avg_confidence": round(row.avg_confidence or 0, 4),
        })

    return {
        "daily_trend": trend_data,
        "modality_distribution": modality_data,
        "period_days": days,
    }


@router.get("/model-analysis")
async def get_model_analysis(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Get model performance analysis data (for model optimization)"""
    modality_analysis = await db.execute(
        select(
            DetectionResult.modality,
            func.count(DetectionResult.id).label("total"),
            func.avg(DetectionResult.confidence).label("avg_confidence"),
            func.avg(DetectionResult.calibrated_confidence).label("avg_calibrated"),
            func.stddev(DetectionResult.confidence).label("std_confidence"),
            func.sum(case((DetectionResult.is_ai_generated == True, 1), else_=0)).label("ai_count"),
            func.sum(case((DetectionResult.risk_level == "high", 1), else_=0)).label("high_risk"),
            func.sum(case((DetectionResult.risk_level == "medium", 1), else_=0)).label("medium_risk"),
            func.sum(case((DetectionResult.risk_level == "low", 1), else_=0)).label("low_risk"),
        )
        .group_by(DetectionResult.modality)
    )

    model_stats = []
    for row in modality_analysis.all():
        total = row.total or 0
        ai_count = int(row.ai_count or 0)
        human_count = total - ai_count

        avg_conf = row.avg_confidence or 0
        avg_cal = row.avg_calibrated or avg_conf
        calibration_effect = round(avg_cal - avg_conf, 4) if avg_cal else 0

        model_stats.append({
            "modality": row.modality,
            "total_samples": total,
            "ai_samples": ai_count,
            "human_samples": human_count,
            "ai_ratio": round(ai_count / max(total, 1), 4),
            "avg_confidence": round(avg_conf, 4),
            "avg_calibrated_confidence": round(avg_cal, 4),
            "calibration_effect": calibration_effect,
            "confidence_std": round(row.std_confidence or 0, 4),
            "risk_distribution": {
                "high": int(row.high_risk or 0),
                "medium": int(row.medium_risk or 0),
                "low": int(row.low_risk or 0),
            },
        })

    confidence_bins = await db.execute(
        select(
            DetectionResult.modality,
            case(
                (DetectionResult.confidence < 0.3, "0-30%"),
                (DetectionResult.confidence < 0.5, "30-50%"),
                (DetectionResult.confidence < 0.7, "50-70%"),
                (DetectionResult.confidence < 0.9, "70-90%"),
                else_="90-100%"
            ).label("bin"),
            func.count(DetectionResult.id).label("count"),
        )
        .group_by(DetectionResult.modality, "bin")
        .order_by(DetectionResult.modality, "bin")
    )

    confidence_distribution = {}
    for row in confidence_bins.all():
        if row.modality not in confidence_distribution:
            confidence_distribution[row.modality] = {}
        confidence_distribution[row.modality][row.bin] = row.count

    arbitration_stats = await db.execute(
        select(
            func.count(DetectionResult.id).label("total_with_warning"),
        ).where(DetectionResult.arbitration_warning.isnot(None))
    )
    arbitration_count = arbitration_stats.scalar() or 0

    return {
        "model_stats": model_stats,
        "confidence_distribution": confidence_distribution,
        "arbitration_warnings": arbitration_count,
        "calibration_params": {
            det_id: {
                "temperature": p.temperature,
                "platt_a": p.platt_a,
                "platt_b": p.platt_b,
                "ece": p.ece,
            }
            for det_id, p in _calibrator.params.items()
        },
    }


@router.get("/detection-contents")
async def get_detection_contents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    modality: str = Query("", description="Filter by modality: text/image/audio"),
    min_confidence: float = Query(0.0, ge=0, le=1, description="Min confidence"),
    max_confidence: float = Query(1.0, ge=0, le=1, description="Max confidence"),
    is_ai: bool = Query(None, description="Filter by AI-generated flag"),
    has_feedback: bool = Query(None, description="Filter by feedback existence"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Get user detection content list (for model training data collection)"""
    query = (
        select(DetectionResult, Task, User)
        .join(Task, DetectionResult.task_id == Task.id)
        .join(User, Task.user_id == User.id)
    )
    count_query = (
        select(func.count(DetectionResult.id))
        .join(Task, DetectionResult.task_id == Task.id)
    )

    if modality:
        query = query.where(DetectionResult.modality == modality)
        count_query = count_query.where(DetectionResult.modality == modality)
    if min_confidence > 0:
        query = query.where(DetectionResult.confidence >= min_confidence)
        count_query = count_query.where(DetectionResult.confidence >= min_confidence)
    if max_confidence < 1.0:
        query = query.where(DetectionResult.confidence <= max_confidence)
        count_query = count_query.where(DetectionResult.confidence <= max_confidence)
    if is_ai is not None:
        query = query.where(DetectionResult.is_ai_generated == is_ai)
        count_query = count_query.where(DetectionResult.is_ai_generated == is_ai)

    total = (await db.execute(count_query)).scalar()
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(desc(DetectionResult.created_at)).offset(offset).limit(page_size)
    )
    rows = result.all()

    contents = []
    for dr, task, user in rows:
        contents.append({
            "id": str(dr.id),
            "task_id": str(dr.task_id),
            "modality": dr.modality,
            "is_ai_generated": dr.is_ai_generated,
            "confidence": round(dr.confidence, 4),
            "calibrated_confidence": round(dr.calibrated_confidence, 4) if dr.calibrated_confidence else None,
            "risk_level": dr.risk_level,
            "raw_scores": dr.raw_scores,
            "model_attribution": dr.model_attribution,
            "input_content": task.input_content[:1000] if task.input_content else None,
            "input_file_url": task.input_file_url,
            "username": user.username,
            "user_role": user.role,
            "created_at": dr.created_at.strftime("%Y-%m-%d %H:%M:%S") if dr.created_at else None,
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "contents": contents,
    }


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", description="Search by username or email"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Get user list (pagination + search)"""
    query = select(User)
    count_query = select(func.count(User.id))

    if search:
        like = f"%{search}%"
        filter_cond = (User.username.like(like)) | (User.email.like(like))
        query = query.where(filter_cond)
        count_query = count_query.where(filter_cond)

    total = (await db.execute(count_query)).scalar()
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(desc(User.created_at)).offset(offset).limit(page_size)
    )
    users = result.scalars().all()

    user_list = []
    for u in users:
        task_count = (await db.execute(
            select(func.count(Task.id)).where(Task.user_id == u.id)
        )).scalar()
        ai_count = (await db.execute(
            select(func.count(DetectionResult.id))
            .join(Task, DetectionResult.task_id == Task.id)
            .where(Task.user_id == u.id, DetectionResult.is_ai_generated == True)
        )).scalar()

        user_list.append({
            "id": str(u.id),
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "quota_remaining": u.quota_remaining,
            "is_blocked": u.is_blocked,
            "subscription_type": u.subscription_type,
            "subscription_expiry": u.subscription_expiry.strftime("%Y-%m-%d") if u.subscription_expiry else None,
            "task_count": task_count,
            "ai_detected_count": ai_count,
            "created_at": u.created_at.strftime("%Y-%m-%d %H:%M:%S") if u.created_at else None,
        })

    return {"total": total, "page": page, "page_size": page_size, "users": user_list}


# ============================================================
# 会员管理
# ============================================================

@router.post("/users/{user_id}/recharge")
async def recharge_user(
    user_id: str,
    amount: int = Query(ge=1, le=99999, description="充值额度"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """为指定用户充值额度"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.quota_remaining += amount
    await db.commit()
    return {"ok": True, "user_id": user_id, "quota_remaining": user.quota_remaining, "added": amount}


@router.post("/users/{user_id}/monthly-card")
async def activate_monthly_card(
    user_id: str,
    plan: str = Query(pattern="^(monthly|quarterly|yearly)$", description="套餐类型"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """为用户开通月卡/季卡/年卡"""
    from datetime import datetime, timedelta
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    now = datetime.now()
    if user.subscription_expiry and user.subscription_expiry > now:
        start = user.subscription_expiry
    else:
        start = now

    days = {"monthly": 30, "quarterly": 90, "yearly": 365}[plan]
    user.subscription_type = plan
    user.subscription_expiry = start + timedelta(days=days)
    # 月卡赠送基础额度
    bonus = {"monthly": 50, "quarterly": 200, "yearly": 1000}[plan]
    user.quota_remaining += bonus
    await db.commit()
    return {
        "ok": True, "user_id": user_id, "plan": plan,
        "expiry": user.subscription_expiry.strftime("%Y-%m-%d %H:%M:%S"),
        "bonus_quota": bonus, "quota_remaining": user.quota_remaining,
    }


@router.post("/users/{user_id}/block")
async def block_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """拉黑/禁用用户"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.is_blocked = True
    await db.commit()
    return {"ok": True, "user_id": user_id, "is_blocked": True}


@router.post("/users/{user_id}/unblock")
async def unblock_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """解除用户禁用"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.is_blocked = False
    await db.commit()
    return {"ok": True, "user_id": user_id, "is_blocked": False}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """删除用户"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="不能删除管理员")
    await db.delete(user)
    await db.commit()
    return {"ok": True, "user_id": user_id, "deleted": True}


# ============================================================
# 支付管理
# ============================================================

from app.models.payment import Payment


@router.post("/payment/submit")
async def submit_payment(
    amount: int = Query(ge=1, le=99999),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用户提交付款通知"""
    payment = Payment(user_id=str(current_user.id), amount=amount, status="pending")
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return {"ok": True, "payment_id": str(payment.id), "amount": amount,
            "message": "付款已提交，等待管理员确认"}


@router.get("/payments")
async def list_payments(
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """管理员查看付款记录"""
    from app.models.payment import Payment
    base = select(Payment, User.username).join(User, Payment.user_id == User.id)
    count_base = select(func.count(Payment.id)).join(User, Payment.user_id == User.id)
    if status_filter:
        base = base.where(Payment.status == status_filter)
        count_base = count_base.where(Payment.status == status_filter)
    base = base.order_by(desc(Payment.created_at)).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(base)).all()
    total = (await db.execute(count_base)).scalar() or 0

    items = []
    for p, uname in rows:
        items.append({
            "id": str(p.id), "user_id": str(p.user_id), "username": uname,
            "amount": p.amount, "status": p.status,
            "created_at": p.created_at.strftime("%Y-%m-%d %H:%M:%S") if p.created_at else None,
            "confirmed_at": p.confirmed_at.strftime("%Y-%m-%d %H:%M:%S") if p.confirmed_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/payments/{payment_id}/confirm")
async def confirm_payment(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """管理员确认收款 → 自动充值"""
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="付款记录不存在")
    if payment.status != "pending":
        raise HTTPException(status_code=400, detail="该付款已处理")

    from datetime import datetime
    payment.status = "confirmed"
    payment.confirmed_at = datetime.now()

    # 自动充值
    r = await db.execute(select(User).where(User.id == payment.user_id))
    user = r.scalar_one_or_none()
    if user:
        user.quota_remaining += payment.amount

    await db.commit()
    return {"ok": True, "payment_id": payment_id, "status": "confirmed",
            "quota_remaining": user.quota_remaining if user else 0}


@router.post("/payments/{payment_id}/reject")
async def reject_payment(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """管理员拒绝付款"""
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="付款记录不存在")
    payment.status = "rejected"
    await db.commit()
    return {"ok": True, "payment_id": payment_id, "status": "rejected"}


@router.get("/detections")
async def list_detections(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    modality: str = Query("", description="Filter by modality"),
    risk_level: str = Query("", description="Filter by risk level"),
    user_id: str = Query("", description="Filter by user ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Get detection record list (pagination + multi-condition filter)"""
    query = (
        select(DetectionResult, Task, User)
        .join(Task, DetectionResult.task_id == Task.id)
        .join(User, Task.user_id == User.id)
    )
    count_query = (
        select(func.count(DetectionResult.id))
        .join(Task, DetectionResult.task_id == Task.id)
        .join(User, Task.user_id == User.id)
    )

    if modality:
        query = query.where(DetectionResult.modality == modality)
        count_query = count_query.where(DetectionResult.modality == modality)
    if risk_level:
        query = query.where(DetectionResult.risk_level == risk_level)
        count_query = count_query.where(DetectionResult.risk_level == risk_level)
    if user_id:
        query = query.where(Task.user_id == user_id)
        count_query = count_query.where(Task.user_id == user_id)

    total = (await db.execute(count_query)).scalar()
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(desc(DetectionResult.created_at)).offset(offset).limit(page_size)
    )
    rows = result.all()

    detection_list = []
    for dr, task, user in rows:
        detection_list.append({
            "id": str(dr.id),
            "task_id": str(dr.task_id),
            "modality": dr.modality,
            "is_ai_generated": dr.is_ai_generated,
            "confidence": round(dr.confidence, 4),
            "calibrated_confidence": round(dr.calibrated_confidence, 4) if dr.calibrated_confidence else None,
            "risk_level": dr.risk_level,
            "model_attribution": dr.model_attribution,
            "arbitration_warning": dr.arbitration_warning,
            "input_content": task.input_content[:500] if task.input_content else None,
            "task_status": task.status,
            "username": user.username,
            "user_role": user.role,
            "created_at": dr.created_at.strftime("%Y-%m-%d %H:%M:%S") if dr.created_at else None,
        })

    return {"total": total, "page": page, "page_size": page_size, "detections": detection_list}


@router.get("/detections/{detection_id}")
async def get_detection_detail(
    detection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Get single detection record detail (with input content, raw scores, explanation report)"""
    result = await db.execute(
        select(DetectionResult, Task, User)
        .join(Task, DetectionResult.task_id == Task.id)
        .join(User, Task.user_id == User.id)
        .where(DetectionResult.id == detection_id)
    )
    row = result.one_or_none()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Detection record not found")

    dr, task, user = row

    explanation = None
    if dr.explanation_report:
        er = dr.explanation_report
        explanation = {
            "suspicious_spans": er.suspicious_spans,
            "feature_contributions": er.feature_contributions,
            "arbitration_reason": er.arbitration_reason,
            "conflicting_signals": er.conflicting_signals,
        }

    return {
        "id": str(dr.id),
        "task_id": str(dr.task_id),
        "modality": dr.modality,
        "is_ai_generated": dr.is_ai_generated,
        "confidence": dr.confidence,
        "calibrated_confidence": dr.calibrated_confidence,
        "confidence_interval": [dr.confidence_interval_lower, dr.confidence_interval_upper],
        "risk_level": dr.risk_level,
        "raw_scores": dr.raw_scores,
        "model_attribution": dr.model_attribution,
        "arbitration_warning": dr.arbitration_warning,
        "explanation": explanation,
        "input_content": task.input_content,
        "task_status": task.status,
        "task_created_at": task.created_at.strftime("%Y-%m-%d %H:%M:%S") if task.created_at else None,
        "task_completed_at": task.completed_at.strftime("%Y-%m-%d %H:%M:%S") if task.completed_at else None,
        "error_message": task.error_message,
        "user": {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role,
        },
        "created_at": dr.created_at.strftime("%Y-%m-%d %H:%M:%S") if dr.created_at else None,
    }


@router.get("/users/{user_id}/detections")
async def get_user_detections(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Get detection records for a specific user"""
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    if not target_user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found")

    count_query = (
        select(func.count(DetectionResult.id))
        .join(Task, DetectionResult.task_id == Task.id)
        .where(Task.user_id == user_id)
    )
    total = (await db.execute(count_query)).scalar()

    query = (
        select(DetectionResult, Task)
        .join(Task, DetectionResult.task_id == Task.id)
        .where(Task.user_id == user_id)
        .order_by(desc(DetectionResult.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = await db.execute(query)
    results = rows.all()

    detection_list = []
    for dr, task in results:
        detection_list.append({
            "id": str(dr.id),
            "task_id": str(dr.task_id),
            "modality": dr.modality,
            "is_ai_generated": dr.is_ai_generated,
            "confidence": round(dr.confidence, 4),
            "risk_level": dr.risk_level,
            "input_content": task.input_content[:300] if task.input_content else None,
            "created_at": dr.created_at.strftime("%Y-%m-%d %H:%M:%S") if dr.created_at else None,
        })

    return {
        "user": {
            "id": str(target_user.id),
            "username": target_user.username,
            "email": target_user.email,
            "role": target_user.role,
            "created_at": target_user.created_at.strftime("%Y-%m-%d %H:%M:%S") if target_user.created_at else None,
        },
        "total": total,
        "page": page,
        "page_size": page_size,
        "detections": detection_list,
    }


@router.post("/export-dataset")
async def export_dataset(
    modality: str = Query("", description="Modality filter"),
    min_confidence: float = Query(0.0, ge=0, le=1),
    max_confidence: float = Query(1.0, ge=0, le=1),
    sample_limit: int = Query(1000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Export training dataset (for model optimization)"""
    query = (
        select(DetectionResult, Task)
        .join(Task, DetectionResult.task_id == Task.id)
        .where(Task.status == "completed")
    )

    if modality:
        query = query.where(DetectionResult.modality == modality)
    if min_confidence > 0:
        query = query.where(DetectionResult.confidence >= min_confidence)
    if max_confidence < 1.0:
        query = query.where(DetectionResult.confidence <= max_confidence)

    result = await db.execute(
        query.order_by(desc(DetectionResult.created_at)).limit(sample_limit)
    )
    rows = result.all()

    dataset = []
    for dr, task in rows:
        dataset.append({
            "id": str(dr.id),
            "modality": dr.modality,
            "is_ai_generated": dr.is_ai_generated,
            "confidence": dr.confidence,
            "calibrated_confidence": dr.calibrated_confidence,
            "risk_level": dr.risk_level,
            "raw_scores": dr.raw_scores,
            "model_attribution": dr.model_attribution,
            "input_content": task.input_content,
            "input_file_url": task.input_file_url,
            "created_at": dr.created_at.strftime("%Y-%m-%d %H:%M:%S") if dr.created_at else None,
        })

    return {
        "total": len(dataset),
        "modality": modality or "all",
        "confidence_range": [min_confidence, max_confidence],
        "dataset": dataset,
    }
