"""数据库服务层 — 替代内存存储"""

from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import async_session
from models.db_models import UserDB, MealDB, FeedbackDB, ConversationDB


class DatabaseService:
    """数据库服务"""

    # ==================== 用户档案 ====================

    async def get_user(self, user_id: str) -> UserDB | None:
        """获取用户档案"""
        async with async_session() as session:
            result = await session.execute(
                select(UserDB).where(UserDB.user_id == user_id)
            )
            return result.scalar_one_or_none()

    async def create_user(self, user_data: dict) -> UserDB:
        """创建用户"""
        async with async_session() as session:
            user = UserDB(**user_data)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    async def update_user(self, user_id: str, user_data: dict) -> UserDB | None:
        """更新用户"""
        async with async_session() as session:
            result = await session.execute(
                select(UserDB).where(UserDB.user_id == user_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                return None

            for key, value in user_data.items():
                if hasattr(user, key):
                    setattr(user, key, value)

            user.updated_at = datetime.now()
            await session.commit()
            await session.refresh(user)
            return user

    async def delete_user(self, user_id: str) -> bool:
        """删除用户"""
        async with async_session() as session:
            result = await session.execute(
                select(UserDB).where(UserDB.user_id == user_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                return False

            await session.delete(user)
            await session.commit()
            return True

    # ==================== 用餐记录 ====================

    async def get_meals(self, user_id: str, days: int = 7) -> list[MealDB]:
        """获取用餐记录"""
        async with async_session() as session:
            cutoff = datetime.now() - timedelta(days=days)
            result = await session.execute(
                select(MealDB)
                .where(MealDB.user_id == user_id)
                .where(MealDB.timestamp >= cutoff)
                .order_by(MealDB.timestamp.desc())
            )
            return list(result.scalars().all())

    async def get_today_meals(self, user_id: str) -> list[MealDB]:
        """获取今日用餐记录"""
        async with async_session() as session:
            today = datetime.now().date()
            result = await session.execute(
                select(MealDB)
                .where(MealDB.user_id == user_id)
                .where(func.date(MealDB.timestamp) == today)
                .order_by(MealDB.timestamp)
            )
            return list(result.scalars().all())

    async def create_meal(self, meal_data: dict) -> MealDB:
        """创建用餐记录"""
        async with async_session() as session:
            meal = MealDB(**meal_data)
            session.add(meal)
            await session.commit()
            await session.refresh(meal)
            return meal

    # ==================== 反馈 ====================

    async def get_feedbacks(self, user_id: str) -> list[FeedbackDB]:
        """获取反馈记录"""
        async with async_session() as session:
            result = await session.execute(
                select(FeedbackDB)
                .where(FeedbackDB.user_id == user_id)
                .order_by(FeedbackDB.timestamp.desc())
            )
            return list(result.scalars().all())

    async def create_feedback(self, feedback_data: dict) -> FeedbackDB:
        """创建反馈"""
        async with async_session() as session:
            feedback = FeedbackDB(**feedback_data)
            session.add(feedback)
            await session.commit()
            await session.refresh(feedback)
            return feedback

    # ==================== 对话历史 ====================

    async def get_conversations(self, user_id: str, limit: int = 50) -> list[ConversationDB]:
        """获取对话历史"""
        async with async_session() as session:
            result = await session.execute(
                select(ConversationDB)
                .where(ConversationDB.user_id == user_id)
                .order_by(ConversationDB.timestamp.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def create_conversation(self, conv_data: dict) -> ConversationDB:
        """创建对话记录"""
        async with async_session() as session:
            conv = ConversationDB(**conv_data)
            session.add(conv)
            await session.commit()
            await session.refresh(conv)
            return conv

    async def delete_conversations(self, user_id: str) -> bool:
        """删除对话历史"""
        async with async_session() as session:
            result = await session.execute(
                select(ConversationDB).where(ConversationDB.user_id == user_id)
            )
            convs = result.scalars().all()
            for conv in convs:
                await session.delete(conv)
            await session.commit()
            return True


# 全局实例
db_service = DatabaseService()
