# StudyPilot 决赛更新技术报告

## 1. 作品定位

StudyPilot 解决的是一个具体的晚间工作流问题：孩子和家长共同确认今晚有哪些任务、哪些事实已经完成、家庭时间窗口是否足够，然后得到一条可以执行并能跨夜恢复的路线。

这不是把模型放在系统中央再寻找用途。Gemma 4 先经过真实边界用例和本地 Native Function Calling 检验。Gemma 4 只负责语义入口，Python 编译最终路线；截止、容量、版本、一致性和写入由确定性程序负责。

## 2. 从模型输入到产品状态

```text
孩子/家长自然语言
        |
        v
Gemma 4 语义提取
  save_intake_draft
  extract_calibration_evidence
        |
        v
Harness 护栏
  工具白名单 / 严格 Schema / 有限轮数
  Schema 修复 / 幂等 / trace
        |
        v
Python 确定性内核
  规则 / 估时 / 截止 / 容量 / 路线
        |
        v
状态机 + SQLite
  版本 / 人类确认 / 长期记忆 / 跨夜恢复
        |
        +--> 孩子端
        +--> 家长端
```

## 3. 页面到代码的对应关系

### P5：测试决定模型职责

`backend/orchestration/lm_studio.py` 负责访问本地 LM Studio，`backend/orchestration/evening.py` 只把自然语言提取为 `save_intake_draft` 的候选事实。真实 FC 预检和 `tests/real_lm/test_evening_intake_fc.py` 验证模型能调用工具并返回结构化语义，但不把日期、优先级和今晚必做交给模型。

### P6：Harness 增加护栏

`backend/orchestration/harness.py` 和 `tool_registry.py` 按工作流阶段只暴露允许工具，检查 Native Function Calling、严格 Pydantic Schema、最多工具轮数、重复 call id、越权工具、读缓存和写入幂等。每次模型/工具交互都写入 trace。护栏的目标是把模型的可用理解接入一个可验证的业务接口，减少随机输出直接破坏状态的机会。

### P7：规则引擎、状态机、长期记忆、人类确认

`backend/domain/planning.py` 与同目录的规则、估时、截止保护和容量恢复模块构成纯 Python 确定性逻辑。`backend/storage/evening_workflow.py`、`family_context.py`、`database.py` 和迁移文件负责事务、版本、幂等、追加式家庭画像和跨夜记录。家长校准先产生候选证据，再由家长确认，确认后的数据才进入后续规划。

### P8：双 Loop

`parent-frontend` 家长端先可以录入学校作业单和家庭观察，`kid-frontend` 孩子端再补充今晚实际知道的任务与完成情况；Gemma 在各自允许的语义入口提取事实，服务层合并并校验，Python 规划器给出路线。孩子执行和睡前复盘产生的状态会回到 SQLite，下一晚读取确认过的家庭记忆。预置按钮只是手动填入固定演示情景，不跳过确认，也不代表自动完成产品决策。

### P9：技术证据

`evidence/function-calling/v14-real-preflight.json` 记录本地模型、加载状态、`tool_use` 和两轮 Native Function Calling；`DE-POLICY-001.json` 记录模型即使读到相关记忆也可能做出错误排序，因此最终路线必须经过确定性验证。四场景、校准、跨夜、截止/容量和双端报告分别对应产品闭环的可检查行为。

### P10：现场材料

`materials/` 中的 V11 PPT 和 V7 视频是冻结的决赛材料。视频不被重新编码，PPT 不被重新生成；它们与本报告和 V14 源码通过 manifest 和 SHA256 绑定。

## 4. 为什么不是纯模型产品

模型适合处理语言中的省略、同义表达和事实提取，但不适合独自承担版本、幂等、容量边界和跨夜写入。把这些职责交给 Harness、Python 规则和 SQLite，产品才能在模型偶尔不稳定时保持可恢复。Gemma 仍然是重要的语义心脏，但它是可控工作流中的一个组件，而不是整个产品。

## 5. 运行与测试

离线测试覆盖 Harness、工具注册、规划、容量恢复、SQLite、跨夜连续性、Demo API、家长校准和前端预置入口。若 LM Studio 已由用户手动启动，则 `scripts/lm_studio_preflight.py` 和 `scripts/run_v14_demo_checks.ps1` 进一步验证真实 Native Function Calling 与 V14 演示场景。

证据只说明代码路径和合成场景的技术行为，不代表真实家庭效果。现场材料中的彩排记录保持原样，不伪造未执行的计时数据。
