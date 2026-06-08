# Mission Generate Options 与 AI 输出契约接入计划

## Summary

当前 `frontend_new` 的 AI 任务生成弹窗提供了三个选择维度：

- `TASK_DIRECTIONS`: 任务方向，例如数据清洗、SQL 分析、可视化报告、Bug 修复、单元测试、API 设计。
- `DIFFICULTIES`: 难度，例如 easy、medium、hard。
- `STYLES`: 任务风格，例如企业工单、项目委托、面试实战、费曼挑战。

但实际请求 `POST /api/v1/missions/generate` 只发送 `role_id` 和 `difficulty`。后端 schema、DB、prompt、response 也只处理这两个字段。结果是：用户选择的 `task_direction` 和 `mission_style` 不会影响 AI 生成内容，前端结果卡片里的风格 badge 只是本地展示，不代表后端真实生成意图。

本计划目标是让这些 UI 选项真正进入后端生成链路，同时约束 AI 返回格式，使前端只消费后端标准 DTO，而不是猜测或解析半结构化 AI 输出。

## Goals

- 让 `task_direction` 和 `mission_style` 从前端传到后端，并影响 AI prompt。
- 后端返回稳定、前端友好的生成任务结构。
- AI 原始输出经过后端 adapter 清洗、补默认值、限制长度后再返回前端。
- 刷新页面后 `/api/v1/user/sync` 能恢复任务方向、生成风格和 AI 展示字段。
- 保持真实 Feynman challenge 仍由 `/api/v1/missions/evaluate` 触发；`mission_style=feynman` 只表示“费曼讲解型任务风格”。
- 保持旧数据兼容，不要求 Alembic。

## Non-Goals

- 不引入异步任务队列或 polling。
- 不改变评审接口 `/api/v1/missions/evaluate` 的核心流程。
- 不让 AI 决定权威字段，例如 `mission_id`、`mock_data_url`、`status`、`reward_xp`、`career_id`。
- 不在本轮重做任务模板检索系统。

## Current State

### Frontend

`frontend_new/src/components/mission/AIMissionGenerator.tsx`

- UI 维护：
  - `direction`
  - `difficulty`
  - `style`
- 生成时只调用：
  - `missionService.generateMissionWithSource(careerId, difficulty)`
- `direction` 未传入 service。
- `style` 只传给 `mapMissionToGenerated(result.mission, style)`，用于前端 card 的 `type` badge。

`frontend_new/src/services/apiClient.ts`

```ts
body: JSON.stringify({ role_id: roleId, difficulty })
```

### Backend

`backend/app/models/schemas.py`

```py
class MissionGenerateRequest(BaseModel):
  role_id: str
  difficulty: str = "beginner"
```

`backend/app/services/mission.py`

- 使用 `role_id` 推断 `career_id`。
- 使用 `difficulty` 计算 `reward_xp`。
- 构造 `MissionContext(role_id, difficulty, task_index, mission_id, user_id)`。

`backend/app/services/agents/subagents/spec.py`

- prompt 只知道：
  - `role_id`
  - catalog template
  - `difficulty`
- 不知道任务方向和任务风格。

## Proposed API Contract

### Request

`POST /api/v1/missions/generate`

```json
{
  "role_id": "mentor_ying",
  "difficulty": "easy",
  "task_direction": "data-cleaning",
  "mission_style": "ticket"
}
```

### Request Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `role_id` | string | yes | 后端 mentor/role id，例如 `mentor_ying`、`mentor_ling` |
| `difficulty` | string | no | `easy`、`medium`、`hard`，兼容旧值 `beginner` |
| `task_direction` | string \| null | no | 任务方向，来自前端 `TASK_DIRECTIONS` |
| `mission_style` | string \| null | no | 任务风格，来自前端 `STYLES` |

### Allowed Values

`task_direction` 建议按职业分组校验。

Data analyst:

- `data-cleaning`
- `sql-analysis`
- `visualization`

Software engineer:

- `bug-fix`
- `unit-test`
- `api-design`

`mission_style`:

- `ticket`: 企业工单
- `project`: 项目委托
- `interview`: 面试实战
- `feynman`: 费曼讲解型

注意：前端当前文案“费曼挑战”建议改为“费曼讲解型”，避免和真实 Feynman challenge 混淆。

### Response

```json
{
  "mission_id": "mvp_mission_data_1",
  "career_id": "career_data_analyst",
  "role_id": "mentor_ying",
  "title": "数据侦探：用户活跃行为空值清洗与流失归因",
  "description": "...",
  "mock_data_url": "http://localhost:8000/mock_data/...",
  "delivery_requirements": ["..."],
  "difficulty": "easy",
  "task_direction": "data-cleaning",
  "mission_style": "ticket",
  "status": "active",
  "reward_xp": 100,
  "reward_skills": ["skill_data_cleaning"],
  "evaluation_criteria": ["..."],
  "display_metadata": {
    "ai_lead": "数据分析主管",
    "business_background": "...",
    "objectives": ["..."],
    "recommended_skills": ["数据清洗", "漏斗分析"],
    "recommended_resources": ["Pandas 缺失值处理", "漏斗分析方法"],
    "estimated_time": "40-60 min"
  }
}
```

### Response Field Ownership

后端权威字段：

- `mission_id`
- `career_id`
- `role_id`
- `mock_data_url`
- `difficulty`
- `task_direction`
- `mission_style`
- `status`
- `reward_xp`
- `reward_skills`

AI 可生成、但由后端清洗后的展示字段：

- `title`
- `description`
- `delivery_requirements`
- `evaluation_criteria`
- `display_metadata.ai_lead`
- `display_metadata.business_background`
- `display_metadata.objectives`
- `display_metadata.recommended_skills`
- `display_metadata.recommended_resources`
- `display_metadata.estimated_time`

## AI Output Contract

AI 不直接返回最终 API response。AI 只返回 mission spec 展示内容，后端将其 normalize 成标准 DTO。

### AI JSON Schema

建议 `MissionSpecSubagent` 要求 AI 返回：

```json
{
  "title": "string",
  "description": "string",
  "business_background": "string",
  "objectives": ["string"],
  "delivery_requirements": ["string"],
  "evaluation_criteria": ["string"],
  "recommended_skills": ["string"],
  "recommended_resources": ["string"],
  "estimated_time": "string"
}
```

### AI Must Not Return

AI 不允许返回或决定：

- `mission_id`
- `role_id`
- `career_id`
- `status`
- `reward_xp`
- `reward_skills`
- `mock_data_url`
- `mock_data_filename`
- `feynman_active`

### Backend Normalization Rules

后端需要新增 adapter，例如：

```py
def normalize_mission_spec(raw: dict[str, Any], fallback_spec: dict[str, Any]) -> NormalizedMissionSpec:
  ...
```

规则：

- 字符串字段：
  - 非字符串时 fallback。
  - trim。
  - 限制最大长度。
- 数组字段：
  - 非数组时 fallback。
  - 只保留字符串。
  - trim。
  - 去空项。
  - 限制数量，例如最多 6 条。
- `objectives` 缺失：
  - 可由 `delivery_requirements` 派生。
- `evaluation_criteria` 缺失：
  - 使用默认评审标准。
- `business_background` 缺失：
  - 使用 `description`。
- `estimated_time` 缺失：
  - 根据 difficulty 默认：
    - easy: `20-30 min`
    - medium: `40-60 min`
    - hard: `60-90 min`

## Backend Implementation Plan

### 1. Extend Pydantic Schemas

File: `backend/app/models/schemas.py`

Add:

- `MissionStyle = Literal["ticket", "project", "interview", "feynman"]`
- `TaskDirection` 可以先用 `str | None` + validator，避免跨职业 Literal 太冗长。
- `MissionDisplayMetadata`

Update:

- `MissionGenerateRequest`
  - `task_direction: str | None = None`
  - `mission_style: MissionStyle | None = None`
- `MissionGenerateResponse`
  - `task_direction`
  - `mission_style`
  - `display_metadata`
- `MissionRecordResponse`
  - `task_direction`
  - `mission_style`
  - `display_metadata`

Validation:

- `task_direction` 只允许已知值。
- 如果 `role_id=mentor_ying`，允许 data analyst directions。
- 如果 `role_id=mentor_ling`，允许 software engineer directions。
- 旧客户端不传时允许 `None`，后端使用职业默认方向。

### 2. Extend ORM and Self-Heal Schema

File: `backend/app/models/orm.py`

Add columns:

- `task_direction = Column(String, nullable=True)`
- `mission_style = Column(String, nullable=True)`
- `display_metadata_json = Column(Text, nullable=False, default="{}")`

Add property:

```py
@property
def display_metadata(self) -> dict[str, Any]:
  ...
```

File: `backend/app/main.py`

`_self_heal_schema()` add:

- `task_direction VARCHAR`
- `mission_style VARCHAR`
- `display_metadata_json TEXT DEFAULT '{}'`

### 3. Extend Mission Context

File: `backend/app/services/agents/base.py`

Extend `MissionContext`:

```py
task_direction: str | None = None
mission_style: str | None = None
```

### 4. Update Mission Service

File: `backend/app/services/mission.py`

Responsibilities:

- Resolve defaults:
  - data analyst default direction: `data-cleaning`
  - software engineer default direction: `bug-fix`
  - default style: `ticket`
- Build `MissionContext` with `task_direction` and `mission_style`.
- Persist:
  - `task_direction`
  - `mission_style`
  - `display_metadata_json`
  - `evaluation_criteria_json` from normalized AI output.
- Return response with the new fields.

Important:

- Existing active mission replacement currently updates all active missions for the user:
  ```py
  .filter_by(user_id=user_id, status="active").update({"status": "failed"})
  ```
  Consider whether this should be scoped to career. If not changed, generating a task in one career will fail active tasks in another career.

### 5. Update Mission Spec Subagent Prompt

File: `backend/app/services/agents/subagents/spec.py`

Add label maps:

```py
TASK_DIRECTION_LABELS = {
  "data-cleaning": "数据清洗",
  "sql-analysis": "SQL 分析",
  "visualization": "可视化报告",
  "bug-fix": "Bug 修复",
  "unit-test": "单元测试",
  "api-design": "API 设计",
}

MISSION_STYLE_LABELS = {
  "ticket": "企业工单",
  "project": "项目委托",
  "interview": "面试实战",
  "feynman": "费曼讲解型",
}
```

Prompt must include:

- `任务方向：{label}`
- `任务风格：{label}`
- style-specific instruction:
  - ticket: 以真实企业工单形式描述，突出问题、限制条件、验收标准。
  - project: 以项目委托形式描述，突出背景、目标、交付物和业务价值。
  - interview: 以面试实战形式描述，突出考察点、边界条件和追问。
  - feynman: 以费曼讲解型任务描述，要求玩家解释关键概念，但不要激活系统 Feynman challenge。

Schema must require the AI display fields listed above.

### 6. Update Mission Orchestrator Result

File: `backend/app/services/orchestrators/mission.py`

Extend `MissionGenerationResult`:

- `business_background`
- `objectives`
- `evaluation_criteria`
- `recommended_skills`
- `recommended_resources`
- `estimated_time`

Or simpler:

- `display_metadata: dict[str, Any]`
- `evaluation_criteria: list[str]`

Recommended:

```py
display_metadata: dict[str, Any]
evaluation_criteria: list[str]
```

### 7. User Sync

File: `backend/app/api/v1/user.py`

For each mission response include:

- `task_direction=m.task_direction`
- `mission_style=m.mission_style`
- `display_metadata=m.display_metadata`

Legacy fallback:

- If no metadata, return defaults based on old fields:
  - `business_background = description`
  - `objectives = delivery_requirements`
  - `recommended_resources = []`
  - `estimated_time = null`

## Frontend Implementation Plan

### 1. Extend Types

Files:

- `frontend_new/src/types/mission.ts`
- `frontend_new/src/services/apiClient.ts`
- `frontend_new/src/services/apiAdapters.ts`

Add to `Mission`:

```ts
taskDirection?: string | null;
missionStyle?: string | null;
aiLead?: string;
recommendedResources?: string[];
estimatedTime?: string;
```

Add backend types:

```ts
display_metadata?: {
  ai_lead?: string | null;
  business_background?: string | null;
  objectives?: string[] | null;
  recommended_skills?: string[] | null;
  recommended_resources?: string[] | null;
  estimated_time?: string | null;
} | null;
```

### 2. Update API Client

File: `frontend_new/src/services/apiClient.ts`

Change:

```ts
generateMission(roleId, difficulty, taskDirection, missionStyle, signal?)
```

Request body:

```ts
{
  role_id: roleId,
  difficulty,
  task_direction: taskDirection,
  mission_style: missionStyle,
}
```

### 3. Update Mission Service

File: `frontend_new/src/services/missionService.ts`

Change:

```ts
generateMissionWithSource(careerId, difficulty, taskDirection, missionStyle)
```

Pass new args to `api.generateMission`.

### 4. Update API Adapter

File: `frontend_new/src/services/apiAdapters.ts`

In `mapBackendMissionToMission`:

- `background = display_metadata.business_background || description`
- `objectives = display_metadata.objectives || delivery_requirements`
- `criteria = evaluation_criteria || DEFAULT_CRITERIA`
- `rewardSkills = backend reward skills mapped to frontend skill ids`
- `recommendedResources = display_metadata.recommended_resources || []`
- `estimatedTime = display_metadata.estimated_time || difficulty default`
- `taskDirection = mission.task_direction`
- `missionStyle = mission.mission_style`
- `aiLead = display_metadata.ai_lead`

### 5. Update AIMissionGenerator

File: `frontend_new/src/components/mission/AIMissionGenerator.tsx`

Change call:

```ts
missionService.generateMissionWithSource(careerId, difficulty, direction, style)
```

Change generated card mapping:

- Use `mission.missionStyle` from backend if present.
- Use `mission.taskDirection` from backend if present.
- Use `mission.aiLead`.
- Use `mission.recommendedResources`.
- Use `mission.estimatedTime`.

Do not use local `style` to claim backend style unless response lacks `mission_style`.

### 6. Update GeneratedMissionCard

File: `frontend_new/src/components/mission/GeneratedMissionCard.tsx`

Add display fields:

- task direction badge
- mission style badge
- AI lead
- estimated time
- recommended resources

Rename style labels:

- `feynman`: `费曼讲解型`

Avoid “费曼挑战” here.

### 7. Update Mission Detail and Submit Pages

Files:

- `frontend_new/src/app/mission/[missionId]/page.tsx`
- `frontend_new/src/app/mission/[missionId]/submit/page.tsx`

Show if available:

- 任务方向
- 生成风格
- 预计耗时
- 推荐资源

Still show:

- mock data download
- evaluation criteria
- delivery requirements

### 8. Preserve Demo Separation

Demo mode can continue using local mock values, but it must be labeled as demo.

Do not let `mission_style=feynman` automatically enter `/feynman/[missionId]`.

## Validation and Tests

### Backend Tests

Add/update tests:

1. Generate request persists options:
   - input `task_direction=data-cleaning`, `mission_style=ticket`
   - response includes both
   - DB row includes both

2. User sync returns options:
   - existing mission with options returns them
   - legacy mission without options returns `None` or defaults safely

3. AI output normalization:
   - complete AI payload maps to response
   - missing `objectives` falls back to `delivery_requirements`
   - missing `evaluation_criteria` uses default
   - non-string array values are filtered

4. Invalid options:
   - invalid `mission_style` returns 422
   - invalid `task_direction` returns 422 or documented fallback

5. Feynman style does not activate Feynman challenge:
   - generated mission has `mission_style=feynman`
   - DB `feynman_active=False`

### Frontend Tests / Checks

1. `npm run build` passes.
2. Click generate:
   - Network request contains `task_direction` and `mission_style`.
3. Generate with each style:
   - card style badge matches backend response.
4. Generate with each direction:
   - request body changes.
   - backend prompt/log contains direction label.
5. Refresh page:
   - `/user/sync` restores `taskDirection/missionStyle/displayMetadata`.
6. `mission_style=feynman`:
   - displays as “费曼讲解型”
   - does not activate real Feynman challenge before evaluation.

## Migration and Compatibility

No Alembic.

Use `_self_heal_schema()`:

```sql
ALTER TABLE mission_records ADD COLUMN task_direction VARCHAR;
ALTER TABLE mission_records ADD COLUMN mission_style VARCHAR;
ALTER TABLE mission_records ADD COLUMN display_metadata_json TEXT DEFAULT '{}';
```

Old frontend remains compatible because response only adds fields.

Old backend clients remain compatible because new request fields are optional.

## Rollout Order

1. Backend schema + ORM + self-heal columns.
2. MissionContext + MissionSpecSubagent prompt/schema.
3. Backend normalize adapter and response DTO.
4. `/user/sync` response.
5. Backend tests.
6. Frontend apiClient + types.
7. Frontend missionService + apiAdapters.
8. AIMissionGenerator + GeneratedMissionCard.
9. Mission detail/submit display.
10. `npm run build` and manual browser verification.

## Key Risks

- AI may still ignore direction/style unless prompt is explicit enough.
- Too-strict AI schema may increase provider retries or fallback usage.
- Existing cached missions may not have metadata; adapter must handle null.
- `mission_style=feynman` may confuse users if wording remains “费曼挑战”.

## Recommended Copy Changes

In `AIMissionGenerator.tsx`:

- `任务风格`
  - `企业工单`
  - `项目委托`
  - `面试实战`
  - `费曼讲解型`

Helper copy:

> 任务风格会影响 AI 生成任务的叙事方式；真正的费曼挑战仍会在任务评审后由系统触发。

