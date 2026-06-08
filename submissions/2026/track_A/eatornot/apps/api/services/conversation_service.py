"""对话状态管理服务 — SQLite 持久化"""

from datetime import datetime
from dataclasses import dataclass, field

from sqlalchemy import select, delete
from core.database import async_session
from models.db_models import ConversationDB


@dataclass
class ChatMessage:
    role: str  # user / assistant / system
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)


class ConversationService:
    """管理多轮对话状态 — 持久化到 SQLite"""

    def __init__(self):
        # 内存缓存，避免频繁查库
        self._cache: dict[str, list[ChatMessage]] = {}

    async def add_message(self, user_id: str, role: str, content: str, metadata: dict = None) -> ChatMessage:
        """添加消息到对话历史"""
        msg = ChatMessage(role=role, content=content, metadata=metadata or {})

        # 写入数据库
        async with async_session() as session:
            db_msg = ConversationDB(
                user_id=user_id,
                role=role,
                content=content,
                timestamp=msg.timestamp,
                extra_data=metadata or {},
            )
            session.add(db_msg)
            await session.commit()

        # 更新缓存
        if user_id not in self._cache:
            self._cache[user_id] = []
        self._cache[user_id].append(msg)
        return msg

    # 同步版本（兼容旧代码）
    def add_message_sync(self, user_id: str, role: str, content: str, metadata: dict = None) -> ChatMessage:
        msg = ChatMessage(role=role, content=content, metadata=metadata or {})
        if user_id not in self._cache:
            self._cache[user_id] = []
        self._cache[user_id].append(msg)
        return msg

    async def get_history(self, user_id: str, limit: int = 50) -> list[ChatMessage]:
        """获取对话历史"""
        # 优先用缓存
        if user_id in self._cache:
            return self._cache[user_id][-limit:]

        # 从数据库加载
        async with async_session() as session:
            result = await session.execute(
                select(ConversationDB)
                .where(ConversationDB.user_id == user_id)
                .order_by(ConversationDB.id)
                .limit(limit)
            )
            rows = result.scalars().all()
            messages = [
                ChatMessage(
                    role=row.role,
                    content=row.content,
                    timestamp=row.timestamp,
                    metadata=row.extra_data or {},
                )
                for row in rows
            ]
            self._cache[user_id] = messages
            return messages

    # 同步版本（兼容旧代码）
    def get_history_sync(self, user_id: str, limit: int = 50) -> list[ChatMessage]:
        messages = self._cache.get(user_id, [])
        return messages[-limit:]

    async def reset_conversation(self, user_id: str) -> bool:
        """重置对话历史"""
        async with async_session() as session:
            await session.execute(
                delete(ConversationDB).where(ConversationDB.user_id == user_id)
            )
            await session.commit()

        self._cache.pop(user_id, None)
        return True

    # 同步版本
    def reset_conversation_sync(self, user_id: str) -> bool:
        self._cache[user_id] = []
        return True

    def reset_all(self) -> None:
        """清除内存缓存（数据库需单独清理）"""
        self._cache.clear()


# 全局实例
conversation_service = ConversationService()
