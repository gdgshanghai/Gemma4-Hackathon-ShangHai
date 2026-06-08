---
career: software_engineer
mission_id: mission_1_bug_hunter
skills:
  - skill_debugging
  - skill_unit_testing
doc_type: concept
related_files:
  - UserService.java
  - UserServiceTest.java
updated: 2026-05-20
---

# 代码调试：核心策略与心法

## TL;DR

- **核心规则**：按"复现 → 定位 → 理解 → 修复"四步走，每一步都有证据，禁止猜测。
- **反例**：跳过复现直接改代码，结果"看似修好了"但根因还在，迟早再炸。
- **在本任务里怎么用**：先在 `UserServiceTest.java` 里写一个能复现 Issue#123 的测试，再修 `UserService.java`，最后让测试由红变绿。

## 1. 调试的核心心法

> "机器永远是对的，错的一定是我。" 摒弃"代码应该能工作"的假设，以证据为导向。

## 2. 四步调试法

### 1) 复现 (Reproduce)

- **目标**：稳定、可靠地让 Bug 再次发生。
- **方法**：确定触发 Bug 的精确输入和环境条件。在"漏洞捕手"任务中，你需要写出能**稳定复现**"用户名含空格导致登录失败"的单元测试。

### 2) 定位 (Locate)

- **目标**：将问题范围从"整个程序"缩小到"几行代码"。
- **方法**：
  - **日志打印**：在关键代码路径插入 `System.out.println`，观察变量值和执行流。
  - **断点调试**：使用 IDE（如 IntelliJ IDEA）的调试器，逐行执行，观察变量变化。这是最强大的工具。
  - **二分法**：如果代码很长，在中间位置检查状态，判断 Bug 发生在前半段还是后半段。

### 3) 理解 (Understand)

- **目标**：搞清楚"为什么这几行代码会产生错误的结果？"
- **方法**：对照代码和你的心理模型。常见根因：
  - **逻辑错误**：`if` 条件写反，循环边界错误。
  - **数据状态不一致**：注册时存了 `"alice "`，登录时却用 `"alice"` 去查（这就是本任务的 Bug）。
  - **假设不成立**：以为数据不为 null，但实际上为 null。

### 4) 修复 (Fix)

- **目标**：用最小的、正确的修改解决问题。
- **方法**：修复后，立即运行第一步写的复现测试，确认 Bug 消失。再运行已有的其他测试，确保未引入回归错误。

## 3. 任务中的应用

在"漏洞捕手"任务中：

- **复现**：你已有 Issue 描述。`UserServiceTest` 就是"复现"步骤的产物。
- **定位**：在 `UserService` 的 `register` 和 `login` 方法中打断点，传入 `"alice "`，观察 `userDatabase` Map 里的 key 到底是什么。
- **理解**：你会发现 Map 的 key 是 `"alice "`，而登录时用 `"alice"` 查不到。根因是 `register` 没有对输入做"标准化"。
- **修复**：在 `register` 中对 `username` 调用 `.trim()`。**思考**：`login` 是否也需要同样处理？这是数据一致性的关键。

## 4. 交付物检查清单

提交前确认：

- [ ] 有一个失败过的测试，能证明 Issue 真实存在。
- [ ] 测试名称能描述业务场景，例如 `loginShouldSucceedWhenRegisteredUsernameHasExtraSpaces`。
- [ ] 修复前测试失败，修复后测试通过。
- [ ] 注册和登录对用户名的处理规则一致。
- [ ] 根因总结能说清"输入标准化不一致"，而不是只写"代码有 Bug"。

## 常见误区

- 只在 `login` 里 `trim()` 会让历史脏数据继续留在系统里。更稳妥是把用户名标准化封装成私有方法，让注册、登录、查重共用同一规则。
- 不要为了通过当前测试而写死 `"alice"`。调试任务考察的是定位与修复通用逻辑，不是处理单个样例。
- 不要修完就走。回归测试是必须的，确保没有破坏其他功能。

## RAG 检索关键词

调试, Debugging, 复现 Bug, 单元测试复现, 根因分析, 输入标准化, trim, Map key 不一致, 用户名空格, 回归测试, UserService.java, UserServiceTest.java, skill_debugging, skill_unit_testing, mission_1_bug_hunter

