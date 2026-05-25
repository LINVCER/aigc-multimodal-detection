"""
批量检测服务 - 管理批量任务状态和处理
"""

import uuid
import json
import asyncio
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from loguru import logger


@dataclass
class BatchState:
    """批量任务状态"""
    batch_id: str
    user_id: str
    status: str = "pending"  # pending | processing | completed | cancelled | partial
    total: int = 0
    completed: int = 0
    results: list = field(default_factory=list)
    created_at: str = ""
    finished_at: Optional[str] = None
    cancelled: bool = False

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'BatchState':
        """从字典创建"""
        return cls(**data)


class BatchService:
    """批量检测服务"""

    def __init__(self, use_redis: bool = False, redis_client=None):
        self.use_redis = use_redis
        self.redis_client = redis_client
        self._memory_store: dict[str, BatchState] = {}

    async def create_batch(self, user_id: str, total: int) -> BatchState:
        """创建新的批量任务"""
        batch_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        state = BatchState(
            batch_id=batch_id,
            user_id=user_id,
            status="pending",
            total=total,
            completed=0,
            results=[],
            created_at=now,
            finished_at=None,
            cancelled=False,
        )

        if self.use_redis and self.redis_client:
            # 存储到Redis
            key = f"batch:{batch_id}"
            await self.redis_client.hset(key, mapping=state.to_dict())
            await self.redis_client.expire(key, 86400)  # 24小时过期
            # 添加到用户批次索引
            await self.redis_client.sadd(f"user_batches:{user_id}", batch_id)
        else:
            # 存储到内存
            self._memory_store[batch_id] = state

        return state

    async def get_batch(self, batch_id: str) -> Optional[BatchState]:
        """获取批量任务状态"""
        if self.use_redis and self.redis_client:
            key = f"batch:{batch_id}"
            data = await self.redis_client.hgetall(key)
            if not data:
                return None
            # Redis返回的是bytes，需要解码
            decoded = {k.decode(): v.decode() for k, v in data.items()}
            # 处理特殊字段
            decoded['total'] = int(decoded.get('total', 0))
            decoded['completed'] = int(decoded.get('completed', 0))
            decoded['cancelled'] = decoded.get('cancelled', 'false') == 'true'
            decoded['results'] = json.loads(decoded.get('results', '[]'))
            return BatchState.from_dict(decoded)
        else:
            return self._memory_store.get(batch_id)

    async def update_batch(self, batch_id: str, **kwargs) -> Optional[BatchState]:
        """更新批量任务状态"""
        state = await self.get_batch(batch_id)
        if not state:
            return None

        # 更新字段
        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)

        if self.use_redis and self.redis_client:
            key = f"batch:{batch_id}"
            # 特殊处理results字段
            update_data = state.to_dict()
            update_data['results'] = json.dumps(update_data['results'])
            update_data['cancelled'] = str(update_data['cancelled']).lower()
            await self.redis_client.hset(key, mapping=update_data)
        else:
            self._memory_store[batch_id] = state

        return state

    async def add_result(self, batch_id: str, result: dict) -> Optional[BatchState]:
        """添加单个检测结果"""
        state = await self.get_batch(batch_id)
        if not state:
            return None

        state.results.append(result)
        state.completed += 1

        # 检查是否全部完成
        if state.completed >= state.total:
            state.status = "completed"
            state.finished_at = datetime.now().isoformat()

        return await self.update_batch(
            batch_id,
            results=state.results,
            completed=state.completed,
            status=state.status,
            finished_at=state.finished_at,
        )

    async def cancel_batch(self, batch_id: str) -> Optional[BatchState]:
        """取消批量任务"""
        return await self.update_batch(
            batch_id,
            cancelled=True,
            status="cancelled",
            finished_at=datetime.now().isoformat(),
        )

    async def get_user_batches(self, user_id: str, limit: int = 20) -> list[BatchState]:
        """获取用户的批量任务列表"""
        if self.use_redis and self.redis_client:
            # 从Redis索引获取批次ID列表
            batch_ids = await self.redis_client.smembers(f"user_batches:{user_id}")
            batches = []
            for batch_id in batch_ids:
                state = await self.get_batch(batch_id.decode())
                if state:
                    batches.append(state)
            # 按创建时间排序
            batches.sort(key=lambda x: x.created_at, reverse=True)
            return batches[:limit]
        else:
            # 从内存过滤
            user_batches = [
                s for s in self._memory_store.values()
                if s.user_id == user_id
            ]
            user_batches.sort(key=lambda x: x.created_at, reverse=True)
            return user_batches[:limit]

    async def delete_batch(self, batch_id: str) -> bool:
        """删除批量任务"""
        if self.use_redis and self.redis_client:
            key = f"batch:{batch_id}"
            state = await self.get_batch(batch_id)
            if state:
                await self.redis_client.srem(f"user_batches:{state.user_id}", batch_id)
            await self.redis_client.delete(key)
        else:
            self._memory_store.pop(batch_id, None)
        return True


# 全局批量服务实例（默认使用内存存储）
batch_service = BatchService()
