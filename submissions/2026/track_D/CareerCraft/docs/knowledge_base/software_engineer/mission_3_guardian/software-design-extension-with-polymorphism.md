---
career: software_engineer
mission_id: mission_3_guardian
skills:
  - skill_software_design
  - skill_refactoring
doc_type: concept
related_files:
  - CouponService.java
  - refactor_design.md
updated: 2026-05-20
---

# 守护与演进：用接口与多态构建可扩展的优惠券系统

## TL;DR

- **核心规则**：用 `Coupon` 接口定义"什么是优惠券"，每种券一个实现类，`CouponService` 作为工厂——遵循开闭原则。
- **反例**：在 `issueCoupon` 里堆 `if-else`，每加一种券都改这个方法。
- **在本任务里怎么用**：按 §2–§3 给出接口、3 种实现和工厂代码，并把架构图写进 `refactor_design.md`。

## 1. 任务挑战：当代码"长大"了

你面对的是典型的"成长中的痛苦"：

- `CouponService.java` 像一个什么都会做的"老师傅"，越来越疲惫。
- 每增加一种新优惠券，你都要钻进这个臃肿方法里小心翼翼地修改。
- 业务方明天要"满减券"，后天要"礼品券"……系统能快速响应吗？

这不是简单的"代码整理"任务，而是一次"架构升级"的机会。目标不是让代码看起来整洁，而是让它**变得**易于扩展。

## 2. 架构升级蓝图：三步走战略

### 第一阶段：代码重构（让现有代码可读）

详见 [code-refactoring-smells-and-solutions.md](code-refactoring-smells-and-solutions.md)。重构后的 `CouponService` 看起来像：

```java
public class CouponService {
    public Coupon issueCoupon(CouponType type) {
        validateCouponType(type);
        double discountValue = calculateDiscountValue(type);
        String code = generateCouponCode(type);
        return new Coupon(code, discountValue);
    }
    // ... 更多小而专的函数
}
```

恭喜，你现在拥有"整洁的手工作坊"。但这还不够。

### 第二阶段：设计抽象（定义"乐高积木"的接口）

核心产出：`Coupon` 接口。

```java
/**
 * 优惠券接口。系统中最核心的抽象。
 * 收银台、订单结算等模块只依赖此接口，无需关心具体券种。
 */
public interface Coupon {
    /** 应用优惠策略，返回优惠后的价格 */
    double applyDiscount(double originalPrice);

    /** 人类可读的描述 */
    String getDescription();

    /** 唯一编码 */
    String getCode();
}
```

为什么需要接口：

- **契约**：告诉全系统"不管你是哪种券，必须能 `applyDiscount`"。
- **解耦**：使用方只和 `Coupon` 接口对话，自由替换或新增券种不影响使用方。

### 第三阶段：实现扩展（建造"乐高工厂"）

#### 3.1 实现具体"积木块"

```java
// 积木 A：固定金额折扣券
public class FixedAmountCoupon implements Coupon {
    private final String code;
    private final double discountAmount;

    public FixedAmountCoupon(String code, double discountAmount) {
        this.code = code;
        this.discountAmount = discountAmount;
    }

    @Override
    public double applyDiscount(double originalPrice) {
        return Math.max(0.01, originalPrice - discountAmount);
    }

    @Override public String getDescription() {
        return String.format("直减券，立减%.2f元", discountAmount);
    }
    @Override public String getCode() { return code; }
}

// 积木 B：百分比折扣券
public class PercentageCoupon implements Coupon {
    private final String code;
    private final double discountRate;

    public PercentageCoupon(String code, double discountRate) {
        this.code = code;
        this.discountRate = discountRate;
    }

    @Override
    public double applyDiscount(double originalPrice) {
        return originalPrice * (1 - discountRate);
    }

    @Override public String getDescription() {
        return String.format("折扣券，%.0f%% off", discountRate * 100);
    }
    @Override public String getCode() { return code; }
}

// 积木 C：满减券（展示如何轻松扩展）
public class FullReductionCoupon implements Coupon {
    private final String code;
    private final double threshold;
    private final double reduction;

    public FullReductionCoupon(String code, double threshold, double reduction) {
        this.code = code;
        this.threshold = threshold;
        this.reduction = reduction;
    }

    @Override
    public double applyDiscount(double originalPrice) {
        if (originalPrice >= threshold) {
            return originalPrice - reduction;
        }
        return originalPrice;
    }
    // getDescription、getCode 同上
}
```

#### 3.2 建造中央工厂：升级 `CouponService`

```java
public class CouponService {
    public Coupon issueCoupon(CouponType type) {
        String code = generateUniqueCode();

        switch (type) {
            case WELCOME10:
                return new FixedAmountCoupon(code, 10.0);
            case DISCOUNT5PERCENT:
                return new PercentageCoupon(code, 0.05);
            case FULL100_MINUS_20:
                return new FullReductionCoupon(code, 100.0, 20.0);
            default:
                throw new IllegalArgumentException("未知的优惠券类型: " + type);
        }
    }
    private String generateUniqueCode() { /* ... */ }
}
```

## 3. 架构优势

| 特性 | 描述 | 业务价值 |
| :--- | :--- | :--- |
| 开闭原则 | 对扩展开放，对修改封闭。加新券不改现有类 | 产品提需求时可以自信地说"明天就能上线" |
| 单一职责 | 每个类只做一件事 | 代码更易读、易测试，Bug 更易定位 |
| 可测试性 | 可独立测试 `FullReductionCoupon.applyDiscount` | 提升质量、降低回归风险 |
| 可复用性 | `Coupon` 接口可被订单、购物车等模块使用 | 避免重复造轮子 |

## 4. refactor_design.md 推荐内容

- **架构图**：用文字描述 `CouponService` 依赖 `Coupon` 接口，以及各具体券类实现该接口的关系。
- **接口定义**：完整的 `Coupon` 接口代码。
- **2–3 种具体实现**：`FixedAmountCoupon`、`PercentageCoupon` 完整代码，并简述如何扩展第三种（如 `FullReductionCoupon`）。
- **工厂说明**：展示新的 `CouponService.issueCoupon` 如何像工厂工作。
- **使用示例**：业务方如何通过 `CouponService` 获取 `Coupon`，调用 `applyDiscount`，无需关心具体券种。

## 5. 多态设计检查点

一个合格的优惠券扩展设计应满足：

- [ ] 新增一种优惠券时新增类，而不是修改大量 `if-else`。
- [ ] 业务方依赖 `Coupon` 抽象，而不是具体实现类。
- [ ] 每种优惠券只负责自己的折扣计算规则。
- [ ] 工厂或注册表负责根据类型创建优惠券对象。
- [ ] 错误类型有清晰异常或错误响应。

## 常见误区

- 过度设计。如果系统只有一种优惠券且短期不会扩展，引入复杂工厂可能过头。本任务需求明确包含多种类型，所以接口、多态合理。
- 工厂里仍写大量 `if-else` 计算折扣，把多态退化成开关。折扣规则应属于具体实现类。
- 接口设计成"上帝接口"，方法太多。保持小而专。

## RAG 检索关键词

多态, 接口设计, Coupon 接口, 工厂模式, 开闭原则, FixedAmountCoupon, PercentageCoupon, FullReductionCoupon, 可扩展设计, CouponService.java, refactor_design.md, skill_software_design, skill_refactoring, mission_3_guardian

