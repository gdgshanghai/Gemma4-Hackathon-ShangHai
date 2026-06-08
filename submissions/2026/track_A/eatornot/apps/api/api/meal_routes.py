"""Meal recording, feedback, and today's status routes."""

from datetime import datetime
from fastapi import APIRouter
from models.meal_record import MealRecord
from services.db_service import db_service

router = APIRouter()


@router.get("/stores/search")
async def search_stores(city: str = "北京", keyword: str = ""):
    """Search nearby McDonald's stores (mock data for demo)."""
    mock_stores = [
        {"storeCode": "1101001", "storeName": f"{city}王府井餐厅", "address": f"{city}市东城区王府井大街88号", "distance": "0.5km", "beCode": "1101001"},
        {"storeCode": "1101002", "storeName": f"{city}西单餐厅", "address": f"{city}市西城区西单北大街120号", "distance": "1.2km", "beCode": "1101002"},
        {"storeCode": "1101003", "storeName": f"{city}三里屯餐厅", "address": f"{city}市朝阳区三里屯路19号", "distance": "2.1km", "beCode": "1101003"},
        {"storeCode": "1101004", "storeName": f"{city}国贸餐厅", "address": f"{city}市朝阳区建国门外大街1号", "distance": "3.5km", "beCode": "1101004"},
        {"storeCode": "1101005", "storeName": f"{city}望京餐厅", "address": f"{city}市朝阳区望京西路", "distance": "4.8km", "beCode": "1101005"},
        {"storeCode": "1101006", "storeName": f"{city}中关村餐厅", "address": f"{city}市海淀区中关村大街", "distance": "5.3km", "beCode": "1101006"},
    ]
    filtered = [s for s in mock_stores if keyword in s["storeName"] or keyword in s["address"]] if keyword else mock_stores
    return {"stores": filtered, "total": len(filtered), "city": city, "is_mock": True}


@router.post("/meal/record", response_model=MealRecord)
async def record_meal(record: MealRecord):
    """Save a meal record."""
    # 生成 ID
    record.id = f"meal-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    if not record.timestamp:
        record.timestamp = datetime.now()

    # 保存到数据库
    await db_service.create_meal(record.model_dump())

    return record


@router.get("/today/status")
async def get_today_status(user_id: str = "demo-user"):
    """Get today's calorie, budget, and indulgence summary."""
    today_meals = await db_service.get_today_meals(user_id)

    total_calories = sum(m.total_calories for m in today_meals)
    total_price = sum(m.total_price for m in today_meals)

    return {
        "date": datetime.now().date().isoformat(),
        "meals_count": len(today_meals),
        "total_calories": round(total_calories, 0),
        "total_spent": round(total_price, 2),
        "meals": [
            {
                "id": m.id,
                "user_id": m.user_id,
                "timestamp": m.timestamp.isoformat(),
                "meal_type": m.meal_type,
                "items": m.items,
                "total_price": m.total_price,
                "total_calories": m.total_calories,
            }
            for m in today_meals
        ],
    }


@router.get("/meal/history")
async def get_meal_history(user_id: str = "demo-user", days: int = 7):
    """Get meal history for a user."""
    meals = await db_service.get_meals(user_id, days)
    return {
        "user_id": user_id,
        "days": days,
        "meals_count": len(meals),
        "meals": [
            {
                "id": m.id,
                "user_id": m.user_id,
                "timestamp": m.timestamp.isoformat(),
                "meal_type": m.meal_type,
                "items": m.items,
                "total_price": m.total_price,
                "total_calories": m.total_calories,
            }
            for m in meals
        ],
    }


@router.post("/feedback")
async def submit_feedback(feedback: dict):
    """Submit post-meal satisfaction feedback. Triggers Reflection Agent."""
    from agents.reflection_agent import ReflectionAgent
    from services.memory_service import MemoryService

    meal_id = feedback.get("meal_id", "")
    satisfaction = feedback.get("satisfaction", 3)
    notes = feedback.get("notes", "")

    # 保存到数据库
    await db_service.create_feedback({
        "user_id": feedback.get("user_id", "demo-user"),
        "meal_id": meal_id,
        "satisfaction": satisfaction,
        "notes": notes,
    })

    # Run Reflection Agent
    reflection = ReflectionAgent()
    result = await reflection.run({
        "meal_id": meal_id,
        "satisfaction": satisfaction,
        "notes": notes,
        "memory_service": MemoryService(),
    })

    return {
        "status": "recorded",
        "message": "Thanks for your feedback! I'll use this to improve future recommendations.",
        "reflection": {
            "insight": result.reasons[0] if result.reasons else "",
            "adjustment": result.data.get("adjustment", "none"),
            "score": result.score,
        },
    }
