"""ActivePlan 版本管理服务 — SQLite 持久化"""

import uuid
import logging
from models.active_plan import ActivePlan, ChangeLogEntry
from models.recommendation import MenuItem
from models.db_models import ActivePlanDB
from core.database import async_session
from sqlalchemy import select, delete

logger = logging.getLogger(__name__)


class ActivePlanService:
    """管理 ActivePlan 的创建、更新和版本控制 — 持久化到 SQLite"""

    def __init__(self):
        # 内存缓存
        self._cache: dict[str, ActivePlan] = {}

    def _plan_to_dict(self, plan: ActivePlan) -> dict:
        """ActivePlan → 可 JSON 序列化的 dict"""
        return {
            "plan_id": plan.plan_id,
            "version": plan.version,
            "items": [i.model_dump() for i in plan.items],
            "nutrition": plan.nutrition,
            "price": plan.price,
            "reasons": plan.reasons,
            "tradeoffs": plan.tradeoffs,
            "change_log": [c.model_dump() for c in plan.change_log],
            "constraints": plan.constraints,
            "title": plan.title,
            "mode": plan.mode,
        }

    def _db_to_plan(self, db_plan: ActivePlanDB) -> ActivePlan:
        """ORM 对象 → ActivePlan"""
        items = [MenuItem(**i) for i in (db_plan.items or [])]
        change_log = [ChangeLogEntry(**c) for c in (db_plan.change_log or [])]
        return ActivePlan(
            plan_id=db_plan.plan_id,
            version=db_plan.version,
            items=items,
            nutrition=db_plan.nutrition or {},
            price=db_plan.price or 0.0,
            reasons=db_plan.reasons or [],
            tradeoffs=db_plan.tradeoffs or [],
            change_log=change_log,
            constraints=db_plan.constraints or [],
            title=db_plan.title or "",
            mode=db_plan.mode or "",
        )

    async def create_plan(self, user_id: str, title: str, mode: str, items: list[MenuItem],
                          reasons: list[str], tradeoffs: list[str]) -> ActivePlan:
        """从推荐方案创建新的 ActivePlan"""
        plan_id = str(uuid.uuid4())[:8]

        nutrition = {
            "calories": sum(i.calories for i in items),
            "protein": sum(i.protein for i in items),
            "fat": sum(i.fat for i in items),
            "carbs": sum(i.carbohydrate for i in items),
            "sodium": sum(i.sodium for i in items),
        }
        price = sum(i.price for i in items)

        plan = ActivePlan(
            plan_id=plan_id,
            version=1,
            items=items,
            nutrition=nutrition,
            price=price,
            reasons=reasons,
            tradeoffs=tradeoffs,
            title=title,
            mode=mode,
        )

        # 写入数据库
        async with async_session() as session:
            db_plan = ActivePlanDB(
                plan_id=plan_id,
                user_id=user_id,
                version=1,
                items=[i.model_dump() for i in items],
                nutrition=nutrition,
                price=price,
                reasons=reasons,
                tradeoffs=tradeoffs,
                change_log=[],
                constraints=[],
                title=title,
                mode=mode,
            )
            session.add(db_plan)
            await session.commit()

        self._cache[plan_id] = plan
        return plan

    # 同步版本（兼容旧调用）
    def create_plan_sync(self, title: str, mode: str, items: list[MenuItem],
                         reasons: list[str], tradeoffs: list[str]) -> ActivePlan:
        plan_id = str(uuid.uuid4())[:8]
        nutrition = {
            "calories": sum(i.calories for i in items),
            "protein": sum(i.protein for i in items),
            "fat": sum(i.fat for i in items),
            "carbs": sum(i.carbohydrate for i in items),
            "sodium": sum(i.sodium for i in items),
        }
        price = sum(i.price for i in items)
        plan = ActivePlan(
            plan_id=plan_id, version=1, items=items,
            nutrition=nutrition, price=price,
            reasons=reasons, tradeoffs=tradeoffs,
            title=title, mode=mode,
        )
        self._cache[plan_id] = plan
        return plan

    async def get_plan(self, plan_id: str) -> ActivePlan | None:
        """获取方案（缓存优先）"""
        if plan_id in self._cache:
            return self._cache[plan_id]

        async with async_session() as session:
            result = await session.execute(
                select(ActivePlanDB).where(ActivePlanDB.plan_id == plan_id)
            )
            db_plan = result.scalar_one_or_none()
            if db_plan:
                plan = self._db_to_plan(db_plan)
                self._cache[plan_id] = plan
                return plan
        return None

    # 同步版本
    def get_plan_sync(self, plan_id: str) -> ActivePlan | None:
        return self._cache.get(plan_id)

    async def refine_plan(self, plan_id: str, new_items: list[MenuItem],
                          what_changed: str, why: str, constraints: list[str]) -> ActivePlan | None:
        """精炼方案，创建新版本"""
        plan = await self.get_plan(plan_id)
        if not plan:
            return None

        new_nutrition = {
            "calories": sum(i.calories for i in new_items),
            "protein": sum(i.protein for i in new_items),
            "fat": sum(i.fat for i in new_items),
            "carbs": sum(i.carbohydrate for i in new_items),
            "sodium": sum(i.sodium for i in new_items),
        }
        new_price = sum(i.price for i in new_items)

        # 计算 delta
        calories_delta = new_nutrition["calories"] - plan.nutrition["calories"]
        price_delta = new_price - plan.price
        protein_delta = new_nutrition["protein"] - plan.nutrition["protein"]
        fat_delta = new_nutrition["fat"] - plan.nutrition["fat"]
        sodium_delta = new_nutrition["sodium"] - plan.nutrition["sodium"]
        carbs_delta = new_nutrition["carbs"] - plan.nutrition["carbs"]

        impact_parts = []
        if calories_delta != 0:
            impact_parts.append(f"热量{'增加' if calories_delta > 0 else '减少'}{abs(calories_delta):.0f}千卡")
        if price_delta != 0:
            impact_parts.append(f"价格{'增加' if price_delta > 0 else '减少'}¥{abs(price_delta):.0f}")
        impact = "，".join(impact_parts) if impact_parts else "无明显变化"

        change = ChangeLogEntry(
            version=plan.version + 1,
            what_changed=what_changed,
            why=why,
            impact=impact,
            calories_delta=calories_delta,
            price_delta=price_delta,
            protein_delta=protein_delta,
            fat_delta=fat_delta,
            sodium_delta=sodium_delta,
            carbs_delta=carbs_delta,
        )

        # 更新内存对象
        plan.version += 1
        plan.items = new_items
        plan.nutrition = new_nutrition
        plan.price = new_price
        plan.change_log.append(change)
        plan.constraints = constraints

        # 更新数据库
        async with async_session() as session:
            result = await session.execute(
                select(ActivePlanDB).where(ActivePlanDB.plan_id == plan_id)
            )
            db_plan = result.scalar_one_or_none()
            if db_plan:
                db_plan.version = plan.version
                db_plan.items = [i.model_dump() for i in new_items]
                db_plan.nutrition = new_nutrition
                db_plan.price = new_price
                db_plan.change_log = [c.model_dump() for c in plan.change_log]
                db_plan.constraints = constraints
                await session.commit()

        self._cache[plan_id] = plan
        return plan

    # 同步版本
    def refine_plan_sync(self, plan_id: str, new_items: list[MenuItem],
                         what_changed: str, why: str, constraints: list[str]) -> ActivePlan | None:
        plan = self._cache.get(plan_id)
        if not plan:
            return None

        new_nutrition = {
            "calories": sum(i.calories for i in new_items),
            "protein": sum(i.protein for i in new_items),
            "fat": sum(i.fat for i in new_items),
            "carbs": sum(i.carbohydrate for i in new_items),
            "sodium": sum(i.sodium for i in new_items),
        }
        new_price = sum(i.price for i in new_items)

        calories_delta = new_nutrition["calories"] - plan.nutrition["calories"]
        price_delta = new_price - plan.price
        protein_delta = new_nutrition["protein"] - plan.nutrition["protein"]
        fat_delta = new_nutrition["fat"] - plan.nutrition["fat"]
        sodium_delta = new_nutrition["sodium"] - plan.nutrition["sodium"]
        carbs_delta = new_nutrition["carbs"] - plan.nutrition["carbs"]

        impact_parts = []
        if calories_delta != 0:
            impact_parts.append(f"热量{'增加' if calories_delta > 0 else '减少'}{abs(calories_delta):.0f}千卡")
        if price_delta != 0:
            impact_parts.append(f"价格{'增加' if price_delta > 0 else '减少'}¥{abs(price_delta):.0f}")
        impact = "，".join(impact_parts) if impact_parts else "无明显变化"

        change = ChangeLogEntry(
            version=plan.version + 1, what_changed=what_changed, why=why,
            impact=impact, calories_delta=calories_delta, price_delta=price_delta,
            protein_delta=protein_delta, fat_delta=fat_delta,
            sodium_delta=sodium_delta, carbs_delta=carbs_delta,
        )

        plan.version += 1
        plan.items = new_items
        plan.nutrition = new_nutrition
        plan.price = new_price
        plan.change_log.append(change)
        plan.constraints = constraints
        return plan

    async def reset_plan(self, plan_id: str) -> bool:
        """删除方案"""
        async with async_session() as session:
            await session.execute(
                delete(ActivePlanDB).where(ActivePlanDB.plan_id == plan_id)
            )
            await session.commit()
        self._cache.pop(plan_id, None)
        return True

    def reset_all(self) -> None:
        """清除内存缓存"""
        self._cache.clear()


# 全局实例
active_plan_service = ActivePlanService()
