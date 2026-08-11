# V14.5 今晚指挥台前端验证

验证日期：2026-07-22；决赛打包复核：2026-08-11
分支：`v14-real-evening-demo`
范围：孩子端、家长端、真实演示闭环与响应式证据；不修改规划器、估时规则或本地模型编排。

## 静态门禁

| 命令 | 结果 |
| --- | --- |
| `kid-frontend: npm test` | 10 个文件，27 个测试通过 |
| `kid-frontend: npm run build` | TypeScript 与 Vite 生产构建通过 |
| `parent-frontend: npm test` | 6 个文件，21 个测试通过 |
| `parent-frontend: npm run build` | TypeScript 与 Vite 生产构建通过 |
| `git diff --check` | 通过；仅有 Windows 换行提示 |
| `决赛现场预检.bat` | 模型、API、SQLite 与两个前端就绪 |

Vitest 仍输出项目已有的 React `act(...)` 提示，不存在测试失败或构建警告导致失败。

## 真实本地模型闭环

- LM Studio 健康状态为 `ready=true`；模型 `gemma-4-26b-a4b-it`，量化 `Q4_K_M`，`loaded=true`，`tool_use=true`。
- 家长端已将固定模拟星期一的七科学校作业单保存到演示数据库。
- 孩子端一键代入预设陈述后真实调用 Gemma，整理约 18.3 秒；本次只有一次 intake 写请求，未进入 `model_unavailable`。
- 学校对照正确补入孩子陈述遗漏的地理作业。今晚窗口 170 分钟，固定事项 0 分钟，今晚必做 110 分钟；未出现历史的 333 分钟结果。
- 路线于 19:30 开始，预计 21:40 结束，预留 20 分钟缓冲和 40 分钟真实余量。历史、生物和道法保留具体后续日期。
- 路线确认后使用默认“全部完成”最小复盘关闭。家长晚间记录随后读到已归档 v6、预计 21:40、真实余量 40 分钟、4 项完成、0 项未完成。
- 家长校准页的“载入示例观察”只填充文本并显示“模拟数据，尚未保存”；本次未提交校准，因此没有新增模型调用或规划参数变更。

## 视觉与响应式门禁

浏览器自动门禁在 `360x800`、`768x1024`、`1440x900`、`1920x1080` 四档，覆盖孩子归档页，以及家长作业单、校准、晚间记录三页：

- 所有页面均满足 `scrollWidth === clientWidth`，未发现越出视口的可见元素。
- 桌面 H1 `36px`、H2 `26px`；手机 H1 `30px`、H2 `24px`，必要文字最小 `15px`。
- 桌面正文 `19px`，手机任务与正文 `18px`；按钮、日期输入和文本区至少 `17px`，按钮和单行输入高度至少 `50px`。
- 固定八张人工截图只覆盖孩子全貌/路线，以及家长作业单/校准；不包含孩子归档页或家长晚间记录，不能作为这两页的人工截图结论。

## 实机发现与修复

1. 家长日期控件在键盘编辑的短暂空值阶段会让 `formatCalendarDate` 抛出 `RangeError`并白屏。现已增加无效日期显示与查询停用保护，并有“清空日期仍可继续使用”回归测试。
2. 孩子演示归档页原显示服务器当天 `session_date`，与固定模拟日期不一致。现改为显示响应中已有的 `planning_date`；真实模式两者一致，不改变业务数据。
3. Chrome 扩展在 Windows 高 DPI 下对部分短页的全页截图出现重复拼接。这是证据捕获问题，页面 DOM 和溢出门禁正常；最终校准页证据已用独立 Playwright Chromium、`deviceScaleFactor=1` 重新生成。

## 截图

以下固定截图的范围仅为孩子全貌/路线和家长作业单/校准；孩子归档页及家长晚间记录由上述四档浏览器自动门禁覆盖，不在这八张截图中。

- `evidence/screenshots/v14-5/kid-overview-1440x900.png`
- `evidence/screenshots/v14-5/kid-overview-360x800.png`
- `evidence/screenshots/v14-5/kid-route-1440x900.png`
- `evidence/screenshots/v14-5/kid-route-360x800.png`
- `evidence/screenshots/v14-5/parent-brief-1440x900.png`
- `evidence/screenshots/v14-5/parent-brief-360x800.png`
- `evidence/screenshots/v14-5/parent-calibration-1440x900.png`
- `evidence/screenshots/v14-5/parent-calibration-360x800.png`

## 结论边界

本轮证明两端前端功能闭环、字号合同和四档布局通过，且真实本地 Gemma 在一次模拟夜晚中成功完成盘点整理。这不是真实孩子使用效果，不支持成绩、拖延改善或通用性声称。
