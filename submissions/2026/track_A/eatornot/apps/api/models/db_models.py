"""数据库模型"""

from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from core.database import Base


class UserDB(Base):
    """用户档案表"""
    __tablename__ = "users"

    user_id = Column(String, primary_key=True)
    name = Column(String, default="")
    height_cm = Column(Float, default=170.0)
    weight_kg = Column(Float, default=65.0)
    age = Column(Integer, default=25)
    sex = Column(String, default="male")
    goal = Column(String, default="lose_weight")
    activity_level = Column(String, default="moderate")
    daily_budget = Column(Float, default=50.0)
    weekly_budget = Column(Float, default=300.0)
    weekly_indulgence_allowance = Column(Integer, default=2)
    taste_preferences = Column(JSON, default=[])
    allergies = Column(JSON, default=[])
    dislikes = Column(JSON, default=[])
    preferred_tone = Column(String, default="gentle_friend")
    meal_schedule = Column(JSON, default={})
    onboarding_complete = Column(Integer, default=0)
    mode = Column(String, default="long_term")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系
    meals = relationship("MealDB", back_populates="user")


class MealDB(Base):
    """用餐记录表"""
    __tablename__ = "meals"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.user_id"))
    timestamp = Column(DateTime, default=datetime.now)
    meal_type = Column(String, default="dinner")
    items = Column(JSON, default=[])
    total_price = Column(Float, default=0.0)
    total_calories = Column(Float, default=0.0)
    total_protein = Column(Float, default=0.0)
    total_fat = Column(Float, default=0.0)
    total_carbs = Column(Float, default=0.0)
    total_sodium = Column(Float, default=0.0)
    plan_mode = Column(String, default="")
    satisfaction = Column(Integer, nullable=True)
    notes = Column(String, default="")

    # 关系
    user = relationship("UserDB", back_populates="meals")


class FeedbackDB(Base):
    """反馈表"""
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"))
    meal_id = Column(String, ForeignKey("meals.id"))
    satisfaction = Column(Integer, default=3)
    notes = Column(String, default="")
    timestamp = Column(DateTime, default=datetime.now)


class ConversationDB(Base):
    """对话历史表"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"))
    role = Column(String, default="user")
    content = Column(String, default="")
    timestamp = Column(DateTime, default=datetime.now)
    extra_data = Column(JSON, default={})  # 使用 extra_data 代替 metadata


class ActivePlanDB(Base):
    """活跃方案表"""
    __tablename__ = "active_plans"

    plan_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.user_id"))
    version = Column(Integer, default=1)
    items = Column(JSON, default=[])
    nutrition = Column(JSON, default={})
    price = Column(Float, default=0.0)
    reasons = Column(JSON, default=[])
    tradeoffs = Column(JSON, default=[])
    change_log = Column(JSON, default=[])
    constraints = Column(JSON, default=[])
    title = Column(String, default="")
    mode = Column(String, default="")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
