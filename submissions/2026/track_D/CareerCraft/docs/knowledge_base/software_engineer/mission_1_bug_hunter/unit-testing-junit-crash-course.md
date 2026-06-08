---
career: software_engineer
mission_id: mission_1_bug_hunter
skills:
  - skill_unit_testing
  - skill_code_quality
doc_type: cookbook
related_files:
  - UserService.java
  - UserServiceTest.java
updated: 2026-05-20
---

# 单元测试与 JUnit 极速入门

## TL;DR

- **核心规则**：每个测试用例只验证一个行为，按 Arrange–Act–Assert（3A）三段写，名字读得出业务意图。
- **反例**：一个测试里塞 5 个 `assert`，挂了不知道哪个先挂。
- **在本任务里怎么用**：用 §5 的模板补全 `UserServiceTest.java`，让"含空格用户名注册后无法登录"的 Bug 可被自动验证。

## 1. 为什么需要单元测试

- **验证正确性**：确保你的代码在当前和未来都按预期工作。
- **安全重构**：修改代码时，有测试套件作为安全网，防止意外破坏现有功能。
- **作为文档**：好的测试展示了方法应该如何被使用，以及它的边界情况。

## 2. JUnit 5 核心注解

```java
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class UserServiceTest {

    @Test
    public void testRegisterNewUser() {
        // 测试代码
    }

    @Test
    public void testRegisterDuplicateUser() {
        // 另一个测试
    }
}
```

## 3. 核心断言 (Assertions)

```java
assertEquals(expected, actual);  // 判断两个值是否相等
assertTrue(condition);            // 条件是否为真
assertFalse(condition);           // 条件是否为假
assertNull(object);               // 对象是否为 null
assertNotNull(object);            // 对象是否不为 null
// 更多：assertSame、assertThrows（测试异常）等
```

## 4. 编写测试的 3A 模式

一个好的测试用例结构清晰：

1. **Arrange（准备）**：设置测试数据，创建对象。
2. **Act（执行）**：调用你要测试的方法。
3. **Assert（断言）**：验证结果是否符合预期。

## 5. 为"漏洞捕手"任务写测试

```java
@Test
public void testRegisterAndLoginWithSpaceInUsername() {
    // 1. Arrange
    UserService service = new UserService();
    String usernameWithSpace = "alice ";
    String password = "secret123";

    // 2. Act
    boolean registerSuccess = service.register(usernameWithSpace, password);
    boolean loginSuccess = service.login("alice", password); // 登录用去空格后的名字

    // 3. Assert
    assertTrue(registerSuccess, "注册应该成功");
    assertFalse(loginSuccess, "登录应该失败，因为用户名不一致"); // 这是 Bug 的表现
}
```

运行这个测试会失败，**复现了 Bug**。任务是修复 `UserService`，让此测试通过。

## 6. 好测试的判断标准

- 只验证一个明确行为。
- 测试名称能读出业务意图。
- Arrange、Act、Assert 三段清晰。
- 不依赖执行顺序。
- 失败时能快速暴露问题原因。

在"漏洞捕手"任务中，测试重点不是覆盖所有登录场景，而是精准覆盖 Issue 描述的异常输入：注册用户名包含首尾空格，登录时使用正常用户名。

## 7. 常用断言选择

- `assertTrue`：验证登录成功、注册成功等布尔结果。
- `assertFalse`：验证重复注册失败、错误密码登录失败。
- `assertEquals`：验证返回值、错误码、积分、连续天数。
- `assertThrows`：验证非法输入会抛出预期异常。

断言应直接对应需求，不要只验证"对象不为空"这种弱条件。

## 常见误区

- 一个测试塞多个断言。失败时定位困难，建议拆成多个用例。
- 测试名叫 `test1` / `testRegister`。看不出业务意图，应描述场景：`shouldFailToLoginWhenUsernameRegisteredWithTrailingSpace`。
- 测试里硬编码大量魔法值。可用常量或参数化测试 (`@ParameterizedTest`)。

## RAG 检索关键词

JUnit 5, 单元测试, 3A 模式, assertTrue, assertFalse, assertEquals, assertThrows, 回归测试, Bug 复现, UserService.java, UserServiceTest.java, skill_unit_testing, skill_code_quality, mission_1_bug_hunter

