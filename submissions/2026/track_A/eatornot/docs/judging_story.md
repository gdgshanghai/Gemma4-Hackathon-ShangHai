# EatOrNot — Judging Story

## The Problem

Busy professionals and students face a daily dilemma: they want convenient fast food, but they also have health goals, budget constraints, and nutritional needs. Current solutions are binary — either you eat healthy or you don't. There's no nuanced decision support.

**"I want McDonald's. I'm trying to lose weight. I'm tired. I don't want to spend too much."**

This is a real, complex human situation that deserves a thoughtful response, not a simple "yes" or "no".

## Our Approach: Multi-Agent Debate

EatOrNot doesn't make decisions for you. Instead, it assembles a team of specialized AI agents that each analyze your situation from a different angle:

| Agent | Perspective |
|-------|-------------|
| Profile Agent | Your personal data and constraints |
| Weight Loss Agent | Your health and fitness goals |
| Nutrition Agent | Food quality and macronutrients |
| Budget Agent | Your financial constraints |
| Craving Agent | Your emotional state and needs |
| Time Context Agent | Your time pressure and convenience |
| Safety Agent | Allergies and health risks |
| Future Simulation Agent | Impact on the rest of your day |

These agents "debate" — each provides their assessment with a score, reasons, and warnings. The system then synthesizes their opinions into three distinct recommendation plans:

1. **Disciplined Plan** — Best for your health goals
2. **Budget-Friendly Plan** — Maximum value for your money
3. **Controlled Indulgence Plan** — A reasonable treat

## Why This Matters

### Transparency
Unlike black-box AI, you see every agent's reasoning. You understand why each recommendation was made.

### Autonomy
We don't tell you what to do. We present options with clear trade-offs. You choose.

### Nuance
Real life isn't binary. Sometimes a controlled indulgence is the right choice for mental health. We acknowledge that.

### Safety
We never auto-order. We check allergies. We warn about extreme dieting. We respect your boundaries.

## Technical Highlights

### LLM with Fallback
Every agent attempts to use the LLM for richer analysis. If the LLM is unavailable (no API key, network issues), it gracefully falls back to rule-based logic. The demo always works.

### Structured Agents
Each agent is a modular class with a standard `run(context) -> AgentResult` interface. This makes the system extensible and testable.

### Skills Architecture
Domain knowledge is organized into skills (weight-loss, nutrition, budget, etc.) with reference documentation. Agents can leverage this knowledge for better decisions.

### Mock MCP
We don't depend on external services for the demo. The McDonald's MCP is fully mocked with realistic data, so the demo works anywhere, anytime.

## Demo Walkthrough

### Setup
```
User: 小明, 24岁, 172cm, 72kg
Goal: 减脂 (lose weight)
Budget: ¥45/day
Mood: Tired, stressed from work
Time: Late evening, needs quick dinner
```

### Input
> "我想吃麦当劳，我在减肥但是好累，预算不多"

### Agent Debate
- Profile Agent: BMI 24.3, daily target 2010 kcal ✅
- Weight Loss Agent: Prefer grilled, avoid sugary drinks ⚠️
- Nutrition Agent: Recommend zero-sugar drinks, corn cup ✅
- Budget Agent: Average combo ~¥17, within budget ✅
- Craving Agent: High craving (tired), allow indulgence ✅
- Time Context Agent: High time pressure, fast food appropriate ✅
- Safety Agent: No allergies detected ✅
- Future Simulation Agent: 2010 kcal remaining ✅

### Three Plans
1. 💪 自律减脂餐 — ¥28, 5kcal, zero sugar
2. 💰 省钱包饱餐 — ¥24, 510kcal, filling
3. 🍔 放纵一下餐 — ¥53, 1350kcal, satisfying

### User Choice
User selects "自律减脂餐", confirms order, and provides feedback.

## Impact

### For Users
- Better food decisions
- Guilt-free indulgence
- Budget awareness
- Nutritional education

### For the Industry
- Shows how AI can assist (not replace) human decisions
- Multi-agent architecture for complex decisions
- Transparent AI reasoning

## Future Vision

- Real McDonald's MCP integration
- Personalized learning from feedback
- More restaurant support
- Social features (share plans with friends)
- Integration with fitness apps

## Conclusion

EatOrNot demonstrates that AI can help with everyday decisions in a way that's transparent, respectful, and nuanced. We don't judge — we help you make informed choices.

**"We don't tell you what to eat. We help you decide if you should."**
