# 主动提醒机制 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让提醒能推送到浏览器通知，提醒消息个性化，避免重复骚扰。

**Architecture:** 前端轮询（现有）+ Notification API 推送 + 后端 LLM 增强提醒消息。每步独立降级。

**Tech Stack:** Browser Notification API / FastAPI / LLM (generate_text)

---

### Task 1: 后端 LLM 增强提醒消息

**Files:**
- Modify: `apps/api/services/reminder_service.py`

- [ ] **Step 1: 在 ReminderService 新增 `_llm_enhance_message` 方法**

```python
async def _llm_enhance_message(self, reminder: Reminder, user, today_meals: list) -> str | None:
    """用 LLM 生成个性化提醒消息。失败返回 None。"""
    from core.llm_client import generate_text

    # 构建今日饮食摘要
    meals_summary = ""
    if today_meals:
        items = []
        for m in today_meals:
            items.append(f"{m.meal_type}: {m.total_calories:.0f}kcal, ¥{m.total_price:.0f}")
        meals_summary = "今日已吃: " + "; ".join(items)
    else:
        meals_summary = "今日尚未用餐"

    # 构建营养状态
    total_cal = sum(m.total_calories for m in today_meals)
    total_protein = sum(m.total_protein for m in today_meals)
    bmr = calculate_bmr(user.weight_kg, user.height_cm, user.age, user.sex)
    tdee = calculate_tdee(bmr, user.activity_level)
    daily_target = get_daily_calorie_target(tdee, user.goal)
    budget_remaining = user.daily_budget - sum(m.total_price for m in today_meals)

    goal_map = {"lose_weight": "减脂", "maintain": "维持", "gain_muscle": "增肌"}

    system_prompt = """你是一个关心用户的饮食助手，正在给用户发提醒。语气温暖亲切，像一个贴心的朋友。
提醒消息要包含具体的营养/预算数据，让用户知道为什么现在该吃饭了。
消息控制在30字以内，简洁有力。"""

    user_prompt = f"""提醒类型: {reminder.reminder_type.value}
基础消息: {reminder.message}
{meals_summary}
热量进度: {total_cal:.0f}/{daily_target:.0f}kcal
蛋白质: {total_protein:.0f}g
预算剩余: ¥{budget_remaining:.0f}
用户目标: {goal_map.get(user.goal, user.goal)}

请生成一条更个性化的提醒消息。"""

    result = await generate_text(system_prompt, user_prompt)
    if result and not result.startswith("[LLM"):
        return result.strip()
    return None
```

- [ ] **Step 2: 在 `check_reminders` 末尾加入 LLM 增强**

在 `check_reminders` 方法的 `return reminders` 之前，加入 LLM 增强：

```python
# LLM 增强提醒消息
for i, reminder in enumerate(reminders):
    enhanced = await self._llm_enhance_message(reminder, user, today_meals)
    if enhanced:
        reminders[i] = Reminder(
            reminder_id=reminder.reminder_id,
            reminder_type=reminder.reminder_type,
            title=reminder.title,
            message=enhanced,
            urgency=reminder.urgency,
            suggested_action=reminder.suggested_action,
            meal_type=reminder.meal_type,
            context=reminder.context,
            created_at=reminder.created_at,
        )

return reminders
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/services/reminder_service.py
git commit -m "feat: ReminderService LLM 增强提醒消息"
```

---

### Task 2: 前端浏览器推送通知

**Files:**
- Create: `apps/web/src/hooks/useNotifications.ts`
- Modify: `apps/web/src/components/ReminderCard.tsx`

- [ ] **Step 1: 创建 useNotifications hook**

创建 `apps/web/src/hooks/useNotifications.ts`：

```typescript
export function useNotifications() {
  const requestPermission = async (): Promise<boolean> => {
    if (!('Notification' in window)) return false
    if (Notification.permission === 'granted') return true
    if (Notification.permission === 'denied') return false
    const result = await Notification.requestPermission()
    return result === 'granted'
  }

  const notify = (title: string, options?: NotificationOptions) => {
    if (!('Notification' in window) || Notification.permission !== 'granted') return
    if (document.visibilityState === 'visible') return // 页面可见时不推送
    const notification = new Notification(title, {
      icon: '/vite.svg',
      ...options,
    })
    notification.onclick = () => {
      window.focus()
      notification.close()
    }
  }

  return { requestPermission, notify, supported: 'Notification' in window }
}
```

- [ ] **Step 2: 在 ReminderCard 中集成通知**

修改 `apps/web/src/components/ReminderCard.tsx`：

1. 导入 hook：
```typescript
import { useNotifications } from '../hooks/useNotifications'
```

2. 在组件内调用 hook 并请求权限：
```typescript
const { requestPermission, notify, supported } = useNotifications()
```

3. 在 `fetchReminders` 的成功回调中，当有新提醒时发送通知。在 `setReminders(filtered)` 之后添加：

```typescript
// 发送浏览器通知
if (supported && filtered.length > 0) {
  requestPermission()
  const latest = filtered[0]
  notify(latest.title, { body: latest.message })
}
```

4. 同时将轮询间隔从 5 分钟缩短到 2 分钟（饭点附近更及时）：
```typescript
const interval = setInterval(fetchReminders, 2 * 60 * 1000)
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/hooks/useNotifications.ts apps/web/src/components/ReminderCard.tsx
git commit -m "feat: 浏览器推送通知 + 提醒轮询2分钟"
```

---

### Task 3: 提醒频率控制（防重复骚扰）

**Files:**
- Modify: `apps/web/src/components/ReminderCard.tsx`

- [ ] **Step 1: 添加通知去重逻辑**

在 ReminderCard 中，维护一个 `notifiedIds` set（与现有的 `dismissedIds` 类似），确保同一提醒只推送一次通知：

在组件内新增 state：
```typescript
const [notifiedIds, setNotifiedIds] = useState<Set<string>>(new Set())
```

修改通知发送逻辑（在 `setReminders(filtered)` 之后）：

```typescript
// 发送浏览器通知（去重）
if (supported) {
  requestPermission()
  const newReminders = filtered.filter(r => !notifiedIds.has(r.reminder_id))
  if (newReminders.length > 0) {
    const latest = newReminders[0]
    notify(latest.title, { body: latest.message })
    setNotifiedIds(prev => new Set([...prev, ...newReminders.map(r => r.reminder_id)]))
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/components/ReminderCard.tsx
git commit -m "feat: 提醒通知去重，避免重复推送"
```

---

## 依赖关系

```
Task 1 (后端 LLM 增强) ──→ 可独立
Task 2 (浏览器推送通知) ──→ 可独立
Task 3 (频率控制) ──→ 依赖 Task 2
```

Task 1 和 Task 2 可并行。Task 3 必须在 Task 2 之后。
