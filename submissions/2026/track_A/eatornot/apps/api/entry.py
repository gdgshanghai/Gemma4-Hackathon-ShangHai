"""Cloudflare Python Worker 入口 — EatOrNot API"""

import json
from workers import WorkerEntrypoint, Response


class Default(WorkerEntrypoint):
    """EatOrNot API Worker"""

    async def fetch(self, request):
        """处理所有 HTTP 请求"""
        url = request.url
        path = url.split("?")[0].split("#")[0] if "?" in url or "#" in url else url
        # Parse URL path properly
        from urllib.parse import urlparse
        parsed = urlparse(request.url)
        path = parsed.path
        method = request.method

        # ---- Health Check ----
        if path == "/health":
            return Response.json({
                "status": "ok",
                "app": "EatOrNot",
                "mock_mcp": True,
                "platform": "cloudflare-workers",
            })

        # ---- Provider Status ----
        if path == "/api/provider/status":
            return Response.json({
                "active_provider": "Mock (Workers)",
                "provider_mode": "mock",
                "fallback_available": False,
                "mcd_mcp_configured": False,
                "message": "Running on Cloudflare Workers with mock data",
            })

        # ---- Recommend ----
        if path == "/api/recommend" and method == "POST":
            return await self._handle_recommend(request)

        # ---- Profile ----
        if path == "/api/profile" and method == "GET":
            user_id = parsed.query.split("user_id=")[-1].split("&")[0] if "user_id=" in parsed.query else "demo-user"
            return await self._handle_get_profile(user_id)

        if path == "/api/profile" and method == "POST":
            return await self._handle_save_profile(request)

        if path == "/api/profile/reset" and method == "POST":
            return Response.json({"success": True})

        # ---- Conversation ----
        if path == "/api/conversation/reset" and method == "POST":
            return Response.json({"success": True})

        # ---- Dashboard ----
        if path == "/api/dashboard":
            return await self._handle_dashboard(request)

        # ---- Reminders ----
        if path == "/api/reminders":
            return Response.json({"reminders": []})

        # ---- Plan Refine ----
        if path == "/api/plan/refine" and method == "POST":
            return Response.json({"error": "Plan refine not available on Workers"})

        # ---- Feedback ----
        if path == "/api/feedback" and method == "POST":
            return Response.json({"status": "ok", "message": "Feedback recorded"})

        # ---- Demo endpoints ----
        if path == "/api/demo/learning":
            return Response.json({"learning_points": 5, "total_observations": 12})

        if path == "/api/demo/metrics":
            return Response.json({"total_decisions": 3, "avg_satisfaction": 4.2})

        # ---- Order ----
        if path == "/api/order/create" and method == "POST":
            return Response.json({"success": False, "message": "Order creation not available on Workers demo"})

        if path == "/api/order/confirm" and method == "POST":
            return Response.json({"order_id": "demo", "status": "confirmed", "message": "Demo order", "is_mock": True})

        # ---- CORS Preflight ----
        if method == "OPTIONS":
            return self._cors_response()

        # ---- 404 ----
        return Response.json({"error": "Not found", "path": path}, status=404)

    def _cors_response(self):
        return Response("", headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        })

    def _json_response(self, data, status=200):
        """返回带 CORS 的 JSON 响应"""
        return Response.json(data, status=status, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        })

    async def _handle_recommend(self, request):
        """推荐接口 — 调用 Gemini API"""
        try:
            body = await request.json()
        except Exception:
            return self._json_response({"error": "Invalid JSON"}, 400)

        message = body.get("message", "帮我选午餐")
        mode = body.get("mode", "quick")

        # 使用 Gemini API 生成推荐
        api_key = self.env.GEMINI_API_KEY if hasattr(self.env, "GEMINI_API_KEY") else None

        if api_key:
            recommendation = await self._call_gemini(api_key, message, mode)
        else:
            recommendation = self._mock_recommend(message)

        return self._json_response(recommendation)

    async def _call_gemini(self, api_key: str, message: str, mode: str) -> dict:
        """调用 Gemini API 生成推荐"""
        import httpx

        system_prompt = """你是 EatOrNot 饮食决策助手。用户会告诉你他们想吃什么，你需要给出 3 个推荐方案。
每个方案包含：title(标题), mode(模式: disciplined/budget_friendly/controlled_indulgence), items(菜品列表), price(价格), calories(热量), pros(优点), cons(缺点), final_reason(推荐理由)。
返回 JSON 格式，包含 plans(数组) 和 summary(总结)。
菜品来自麦当劳菜单，给出真实的价格和热量估算。"""

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "gemma-4-31b-it",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": message},
                        ],
                        "response_format": {"type": "json_object"},
                    },
                    timeout=30.0,
                )
                result = resp.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

                # 尝试解析 JSON
                try:
                    parsed = json.loads(content)
                    if "plans" in parsed:
                        # 补全 plans 的必要字段
                        for i, plan in enumerate(parsed["plans"]):
                            plan.setdefault("id", f"plan-{i+1}")
                            plan.setdefault("mode", ["disciplined", "budget_friendly", "controlled_indulgence"][i % 3])
                            plan.setdefault("items", [])
                            plan.setdefault("estimated_price", plan.get("price", 25))
                            plan.setdefault("estimated_calories", plan.get("calories", 500))
                            plan.setdefault("protein", 20)
                            plan.setdefault("fat", 10)
                            plan.setdefault("carbohydrate", 50)
                            plan.setdefault("sodium", 800)
                            plan.setdefault("budget_impact", f"占日预算约{30+i*10}%")
                            plan.setdefault("calorie_impact", f"占日热量约{20+i*5}%")
                            plan.setdefault("indulgence_impact", f"{'低' if i==0 else '中' if i==1 else '高'}")
                            plan.setdefault("pros", plan.get("pros", []))
                            plan.setdefault("cons", plan.get("cons", []))
                            plan.setdefault("agent_votes", [])
                            plan.setdefault("safety_warnings", [])
                            plan.setdefault("final_reason", plan.get("final_reason", "推荐"))
                            # 清理多余字段
                            for k in ["price", "calories"]:
                                plan.pop(k, None)
                        parsed.setdefault("user_id", "demo-user")
                        parsed.setdefault("agent_debate", [])
                        parsed.setdefault("safety_warnings", [])
                        parsed.setdefault("summary", parsed.get("summary", ""))
                        return parsed
                except json.JSONDecodeError:
                    pass

                # 如果 JSON 解析失败，返回 mock
                return self._mock_recommend(message)

        except Exception as e:
            return self._mock_recommend(message)

    def _mock_recommend(self, message: str) -> dict:
        """Mock 推荐数据（降级方案）"""
        return {
            "user_id": "demo-user",
            "plans": [
                {
                    "id": "plan-1",
                    "title": "💪 自律之选",
                    "mode": "disciplined",
                    "items": [
                        {"name": "板烧鸡腿堡", "item_code": "M001", "category": "burger", "price": 22, "calories": 410, "protein": 25, "fat": 12, "carbohydrate": 45, "sodium": 750, "tags": ["高蛋白"]},
                        {"name": "玉米杯", "item_code": "M002", "category": "side", "price": 8, "calories": 80, "protein": 2, "fat": 1, "carbohydrate": 18, "sodium": 50, "tags": ["低脂"]},
                        {"name": "零度可乐", "item_code": "M003", "category": "drink", "price": 7, "calories": 0, "protein": 0, "fat": 0, "carbohydrate": 0, "sodium": 20, "tags": ["零卡"]},
                    ],
                    "estimated_price": 37, "estimated_calories": 490, "protein": 27, "fat": 13, "carbohydrate": 63, "sodium": 820,
                    "budget_impact": "占日预算74%", "calorie_impact": "占日热量24%", "indulgence_impact": "低",
                    "pros": ["高蛋白", "低热量", "控糖"], "cons": ["味道偏淡"],
                    "agent_votes": [], "safety_warnings": [], "final_reason": "高蛋白低热量，减脂首选",
                },
                {
                    "id": "plan-2",
                    "title": "💰 省钱套餐",
                    "mode": "budget_friendly",
                    "items": [
                        {"name": "麦香鸡", "item_code": "M004", "category": "burger", "price": 12, "calories": 360, "protein": 14, "fat": 16, "carbohydrate": 40, "sodium": 680, "tags": ["性价比"]},
                        {"name": "小薯条", "item_code": "M005", "category": "side", "price": 7, "calories": 230, "protein": 3, "fat": 11, "carbohydrate": 29, "sodium": 160, "tags": []},
                    ],
                    "estimated_price": 19, "estimated_calories": 590, "protein": 17, "fat": 27, "carbohydrate": 69, "sodium": 840,
                    "budget_impact": "占日预算38%", "calorie_impact": "占日热量29%", "indulgence_impact": "中",
                    "pros": ["价格实惠", "经典搭配"], "cons": ["热量偏高"],
                    "agent_votes": [], "safety_warnings": [], "final_reason": "最便宜的饱腹方案",
                },
                {
                    "id": "plan-3",
                    "title": "🎉 快乐套餐",
                    "mode": "controlled_indulgence",
                    "items": [
                        {"name": "巨无霸", "item_code": "M006", "category": "burger", "price": 25, "calories": 530, "protein": 26, "fat": 28, "carbohydrate": 46, "sodium": 950, "tags": ["经典"]},
                        {"name": "中薯条", "item_code": "M007", "category": "side", "price": 11, "calories": 340, "protein": 4, "fat": 16, "carbohydrate": 42, "sodium": 230, "tags": []},
                        {"name": "可口可乐(中)", "item_code": "M008", "category": "drink", "price": 8, "calories": 140, "protein": 0, "fat": 0, "carbohydrate": 35, "sodium": 15, "tags": []},
                    ],
                    "estimated_price": 44, "estimated_calories": 1010, "protein": 30, "fat": 44, "carbohydrate": 123, "sodium": 1195,
                    "budget_impact": "占日预算88%", "calorie_impact": "占日热量50%", "indulgence_impact": "高",
                    "pros": ["经典搭配", "满足感强"], "cons": ["热量高", "钠超标"],
                    "agent_votes": [], "safety_warnings": ["热量超过日目标50%"], "final_reason": "辛苦一天，犒劳自己",
                },
            ],
            "agent_debate": [],
            "summary": f"基于你的需求「{message}」，智囊团为你准备了 3 个方案：自律之选（低卡高蛋白）、省钱套餐（性价比之王）、快乐套餐（犒劳自己）。",
            "safety_warnings": [],
        }

    async def _handle_get_profile(self, user_id: str):
        """获取用户档案"""
        # 尝试从 D1 读取
        try:
            result = await self.env.DB.prepare(
                "SELECT * FROM users WHERE user_id = ?"
            ).bind(user_id).run()
            if result.results:
                user = result.results[0]
                return self._json_response({
                    "user_id": user.get("user_id", user_id),
                    "name": user.get("name", "用户"),
                    "height_cm": user.get("height_cm", 170),
                    "weight_kg": user.get("weight_kg", 65),
                    "age": user.get("age", 25),
                    "sex": user.get("sex", "male"),
                    "goal": user.get("goal", "lose_weight"),
                    "activity_level": user.get("activity_level", "moderate"),
                    "daily_budget": user.get("daily_budget", 50),
                    "weekly_budget": user.get("weekly_budget", 300),
                    "weekly_indulgence_allowance": user.get("weekly_indulgence_allowance", 2),
                    "taste_preferences": json.loads(user.get("taste_preferences", "[]")),
                    "allergies": json.loads(user.get("allergies", "[]")),
                    "dislikes": json.loads(user.get("dislikes", "[]")),
                    "preferred_tone": user.get("preferred_tone", "gentle_friend"),
                    "meal_schedule": json.loads(user.get("meal_schedule", "{}")),
                    "onboarding_complete": bool(user.get("onboarding_complete", 0)),
                    "mode": user.get("mode", "long_term"),
                })
        except Exception:
            pass

        # 默认返回 demo 用户
        return self._json_response({
            "user_id": user_id, "name": "Demo用户", "height_cm": 170, "weight_kg": 65,
            "age": 25, "sex": "male", "goal": "lose_weight", "activity_level": "moderate",
            "daily_budget": 50, "weekly_budget": 300, "weekly_indulgence_allowance": 2,
            "taste_preferences": [], "allergies": [], "dislikes": [],
            "preferred_tone": "gentle_friend", "meal_schedule": {},
            "onboarding_complete": True, "mode": "quick",
        })

    async def _handle_save_profile(self, request):
        """保存用户档案到 D1"""
        try:
            body = await request.json()
        except Exception:
            return self._json_response({"error": "Invalid JSON"}, 400)

        user_id = body.get("user_id", "demo-user")

        try:
            # 先删除旧记录再插入
            await self.env.DB.prepare("DELETE FROM users WHERE user_id = ?").bind(user_id).run()
            await self.env.DB.prepare(
                """INSERT INTO users (user_id, name, height_cm, weight_kg, age, sex, goal,
                   activity_level, daily_budget, weekly_budget, weekly_indulgence_allowance,
                   taste_preferences, allergies, dislikes, preferred_tone, meal_schedule,
                   onboarding_complete, mode)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
            ).bind(
                user_id, body.get("name", ""), body.get("height_cm", 170),
                body.get("weight_kg", 65), body.get("age", 25), body.get("sex", "male"),
                body.get("goal", "lose_weight"), body.get("activity_level", "moderate"),
                body.get("daily_budget", 50), body.get("weekly_budget", 300),
                body.get("weekly_indulgence_allowance", 2),
                json.dumps(body.get("taste_preferences", [])),
                json.dumps(body.get("allergies", [])),
                json.dumps(body.get("dislikes", [])),
                body.get("preferred_tone", "gentle_friend"),
                json.dumps(body.get("meal_schedule", {})),
                1 if body.get("onboarding_complete") else 0,
                body.get("mode", "long_term"),
            ).run()
        except Exception as e:
            pass  # D1 可能还没建表

        return self._json_response(body)

    async def _handle_dashboard(self, request):
        """今日仪表盘"""
        return self._json_response({
            "date": "2026-06-05",
            "meal_status": {
                "breakfast": "recorded",
                "lunch": "recorded",
                "dinner": {"recorded": False},
            },
            "nutrition": {"calories": 850, "target": 2000},
            "total_spent": 38,
            "next_meal_suggestion": {
                "meal_type": "dinner",
                "message": "晚餐时间到了！点击查看推荐",
            },
        })
