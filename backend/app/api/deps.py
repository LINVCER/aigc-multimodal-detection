from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.services.auth_service import decode_token
from app.models.user import User

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的凭证")

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 Token 类型")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="凭证缺失用户标识")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    return user


async def get_current_teacher(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("teacher", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅教师可访问")
    return current_user


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可访问")
    return current_user


QUOTA_COSTS = {
    "text": 1,
    "image": 1,
    "audio": 1,
    "tampering": 2,
    "thesis": 2,
    "multimodal": 3,
    "assistant": 0,
}


def require_quota(modality: str):
    """返回指定模态的额度检查依赖"""
    async def _check(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> User:
        cost = QUOTA_COSTS.get(modality, 1)
        if cost == 0:
            return current_user
        if current_user.quota_remaining < cost:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"额度不足：需要 {cost}，剩余 {current_user.quota_remaining}",
            )
        return current_user
    return _check


async def deduct_quota(
    modality: str,
    db: AsyncSession,
    user: User,
) -> None:
    """扣除指定模态的检测额度"""
    cost = QUOTA_COSTS.get(modality, 1)
    if cost == 0:
        return
    user.quota_remaining = max(0, user.quota_remaining - cost)
    await db.flush()
