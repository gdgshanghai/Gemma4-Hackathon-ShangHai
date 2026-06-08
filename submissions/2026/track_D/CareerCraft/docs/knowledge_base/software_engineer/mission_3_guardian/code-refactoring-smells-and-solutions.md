---
career: software_engineer
mission_id: mission_3_guardian
skills:
  - skill_refactoring
  - skill_code_quality
doc_type: cookbook
related_files:
  - CouponService.java
  - refactor_design.md
updated: 2026-05-20
---

# 代码重构：识别"坏味道"与解决方案

## TL;DR

- **核心规则**：先用测试固定行为，再按"提炼函数 → 引入枚举 → 抽取配置"的顺序小步重构。
- **反例**：没测试就动刀，重构完功能坏了都不知道。
- **在本任务里怎么用**：按 §4 的步骤改造 `CouponService.java`，把坏味道的修复路径写进 `refactor_design.md`。

## 1. 识别代码"坏味道"

任务中的 `CouponService` 存在以下典型坏味道：

### 过长方法 (Long Method)

- **症状**：`issueCoupon` 做了太多事（参数校验、逻辑判断、生成编码、模拟保存）。
- **危害**：难以理解、测试和维护。

### 重复代码 (Duplicated Code)

- **症状**：相同的字符串常量（如 `"WELCOME10"`）散落在各处。
- **危害**：修改时需要找到所有地方，极易出错。

### 魔法数字 / 字符串 (Magic Number/String)

- **症状**：`"WELCOME10"`、`10.0`、`0.05` 等直接硬编码在逻辑中。
- **危害**：含义不明确，修改时需深入逻辑，容易写错。

### 单一职责违背 (Single Responsibility Principle)

- **症状**：一个类既负责优惠券逻辑，又负责模拟数据库操作。
- **危害**：牵一发而动全身，难以复用。

## 2. 重构工具箱

### 提炼函数 (Extract Method)

```java
// 重构前
public void longMethod() {
    // 步骤 A ... 50 行
    // 步骤 B ... 30 行
}

// 重构后
public void longMethod() {
    doStepA();
    doStepB();
}

private void doStepA() { /* 步骤 A */ }
private void doStepB() { /* 步骤 B */ }
```

### 引入常量 / 枚举 (Introduce Constant/Enum)

```java
// 重构前
if ("WELCOME10".equals(couponType)) { /* ... */ }

// 重构后
public enum CouponType { WELCOME10, DISCOUNT5PERCENT }

if (CouponType.WELCOME10.equals(couponType)) { /* ... */ }
```

### 抽取配置

将折扣金额、类型映射等放入配置文件、枚举或独立配置类中。

## 3. 针对任务的重构思路

1. 将 `issueCoupon` 拆分为：`validateInput`、`determineCouponValue`、`generateCouponCode`、`persistCoupon` 等小方法。
2. 创建 `CouponType` 枚举，定义类型和对应基础价值。
3. 进一步思考：校验、计算、持久化是否应该分离到不同的类？这就引出多态设计，详见 [software-design-extension-with-polymorphism.md](software-design-extension-with-polymorphism.md)。

## 4. 重构安全步骤

重构前先写测试，确保原有行为被保护。推荐顺序：

1. 用测试固定现有发券行为。
2. 提取输入校验方法。
3. 提取优惠券类型和金额配置。
4. 提取券码生成逻辑。
5. 提取持久化或保存逻辑。
6. 运行测试，确认行为没有变化。
7. 再考虑引入接口、多态或工厂。

## 5. refactor_design.md 检查清单

提交前确认：

- [ ] 列出原代码的坏味道。
- [ ] 每个重构动作解决了什么问题。
- [ ] 新结构如何支持新增优惠券类型。
- [ ] 哪些测试证明重构没有破坏原功能。

## 常见误区

- 没测试就重构。等于盲目改代码，无法证明行为一致。
- 一口气把所有问题都改了。小步重构 + 频繁运行测试才是安全做法。
- 把"重构"和"加功能"混在一起提交。两者应分开提交，便于回滚和评审。

## RAG 检索关键词

代码坏味道, 重构, 巨型方法, 硬编码, 单一职责, 提取方法, CouponService.java, CouponType, 开闭原则, refactor_design.md, skill_refactoring, skill_code_quality, mission_3_guardian

