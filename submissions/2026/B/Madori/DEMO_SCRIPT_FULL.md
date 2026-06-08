**中文 + EN narration** · 详尽版（≤5:00）· 简版见 [DEMO_SCRIPT.md](DEMO_SCRIPT.md)

# Madori — Demo 视频详尽分镜（目标 4:45，硬上限 5:00）

> 录制前：`./run.sh samples/madorizu_1f.png` 跑出 `web/madori.html`，浏览器全屏打开。准备一张脏图结果备切换（如 `hk_greenview.jpg`）+ 技术报告的架构图截图。
> 节奏原则：**采光给足、过场快切**；每段旁白控制在画面动作时长内。EN 行可做字幕或英文配音。

---

## 0:00–0:30 ｜痛点 Hook
- **画面**：密集户型图特写缓慢推近 → 浮层字"这张图，你真看得懂吗？"
- **旁白**：你租房、买房，最大的人生决定，就对着这样一张图做出。但图上写了什么、缺了什么、哪里有坑——多数人看不懂。
- **EN**: You make the biggest decision of your life — renting or buying — in front of a drawing like this. What it says, what's missing, where the traps are — most people can't read it.

## 0:30–1:00 ｜一句话产品 + 喂图（隐私）
- **画面**：终端跑 `./run.sh samples/madorizu_1f.png`（或直接开 madori.html 入场）→ 秒级出四视图页
- **操作**：展示"一张图进 → 结果出"，镜头扫过顶部 `STUDY MODEL × GEMMA READING`
- **旁白**：Madori 用**本地 Gemma 4**，像建筑师一样读懂这张图，把专业分析直接画在图上。全程在你电脑跑，户型图不上传云端。
- **EN**: Madori uses **local Gemma 4** to read this plan like an architect and draw the analysis right onto it — all on your machine, the plan never leaves your computer.

## 1:00–1:35 ｜📖 解读：房间识别 + 联动 + 五镜头
- **画面**：停在 📖 解读 tab
- **操作**：① 依次点右侧房间 chip（客厅→卧室→厨房），每点一个，3D 里对应房间**实时高亮**；② 向下滚动露出五镜头标题（动线/采光/无障碍/走读/批评）
- **旁白**：它先读出每个房间，再用大白话从五个专业镜头讲给你听——动线、采光、无障碍、生活走读、设计批评。点哪个房间，模型里就亮哪个，左右联动。
- **EN**: It identifies every room, then explains it through five expert lenses — circulation, daylight, accessibility, a daily-life walkthrough, and a design critique. Click any room and it lights up in the model — the panel and the 3D are linked.

## 1:35–2:20 ｜☀ 采光（核心，给足时长）⭐
- **画面**：点 ☀ 采光 tab → 相机自动俯视压平成平面分区图
- **操作**：① 慢慢**转罗盘改北朝向**，镜头停在房间颜色**实时重算**的瞬间；② 指一下色例：南向暖橙 / 东西黄 / 北向蓝 / 内间灰
- **旁白**：建筑师瞄一眼朝向就判出采光，普通人看不出。你只要选个北方向——南向暖橙是好、北向冷蓝是弱、没窗的内间是灰。**注意：这是按朝向和太阳路径几何算出来的事实，转一下朝向就实时重算，不是模型瞎猜的数字。**
- **EN**: An architect glances at orientation and judges daylight; you can't. Just set north — south is warm orange (good), north cool blue (weak), windowless interior gray. **This is a fact computed from orientation and sun path — it recomputes live as you rotate north. Not a guessed number.**
- **录制提示**：这段是全片最强差异点，把"转朝向→颜色变"录清楚，必要时慢放。

## 2:20–2:45 ｜🚶 动线
- **画面**：点 🚶 动线 tab
- **操作**：镜头跟随从玄关出发的**路径线** + 到达顺序编号 1→2→3
- **旁白**：进门后怎么走，一条线一眼看清——从玄关出发，到各房间的先后顺序都标了号。
- **EN**: How you move once inside — one line from the entrance, with each room numbered in arrival order.

## 2:45–3:10 ｜♿ 无障碍
- **画面**：点 ♿ 无障碍 tab
- **操作**：镜头停在标色的关注点：湿区、玄关高差、过窄通行
- **旁白**：对老人、轮椅，这个家哪里可能不友好——湿区、门口高差、过窄的通道，直接标出来。在实地看房前就能判断。
- **EN**: For the elderly or wheelchair users, where this home may be unfriendly — wet zones, entrance level changes, passages too narrow — flagged before you even visit.

## 3:10–3:40 ｜3D 白模交互 + 面积校准
- **画面**：回 📖 解读
- **操作**：① 拖"**平面 ⟷ 立体**"滑块，平面立起成白色体块；② 拖拽旋转、滚轮缩放，展示玻璃窗、墙体、接触阴影；③ 右侧"**实用面积校准**"框输入真实㎡，模型按真实尺寸标定
- **旁白**：拖一下滑块，平面图立起来变成 3D 白模，亲眼看到这个家的体量和层次。知道实用面积，还能一键校准到真实尺寸。
- **EN**: Drag the slider and the flat plan rises into a 3D white model — see the home's volume with your own eyes. Know the floor area? Calibrate it to real dimensions in one field.

## 3:40–4:05 ｜诚实工程（差异化亮点）
- **画面**：切到一张**脏图**（hk_greenview）的结果——3D 退成白色外框 + 顶部"⚠ 几何为估算"+ "房间识别与解读不受影响"
- **旁白**：图读不准时，它**诚实降级**——不画一个好看但骗你的精细模型，而是退成外框、标清楚"这是估算"。**诚实，是这个产品的一部分。**
- **EN**: When a plan can't be read accurately, it **downgrades honestly** — instead of a pretty but misleading model, it falls back to an outline and says "this is an estimate." Honesty is part of the product.

## 4:05–4:40 ｜技术亮点：Gemma 编排 + 双引擎
- **画面**：① 技术报告的 Mermaid 架构图；② 一行字幕"理解归 Gemma · 计算归代码"
- **旁白**：核心不是把图丢给模型要答案。**Gemma 4 当编排大脑**：先抽一次结构、锁成上下文、各镜头共用同一套房间名（防漂移）；理解和判断交给 Gemma，精确几何交给代码。本地小模型保隐私，云端大模型提精度——**始终是 Gemma 4**。
- **EN**: The core isn't dumping the image at a model for an answer. **Gemma 4 is the orchestrating brain**: extract structure once, lock it as context, run every lens on the same room names (no drift); understanding goes to Gemma, exact geometry to code. Local model for privacy, cloud for precision — always Gemma 4.

## 4:40–5:00 ｜社会价值收尾
- **画面**：使命文案上浮
- **旁白**：普通人对着户型图做出人生最大的决定，却最读不懂它。Madori 用 Gemma 4 的眼睛，把建筑师的读图能力——**免费、私密、诚实**地，交到每一个人手里。
- **EN**: People make the biggest decision of their lives in front of a plan they can least read. Madori uses the eyes of Gemma 4 to hand an architect's plan-reading ability — free, private, honest — to everyone.

---

## 录制 checklist
- [ ] 提前跑好 `madori.html`（madorizu_1f，确认 GEOM high 四视图正常）+ 一张脏图结果备切换
- [ ] 浏览器全屏、隐藏书签栏、关通知、调好窗口比例
- [ ] **采光段**先彩排"转朝向→颜色实时重算"能流畅演示（全片最强镜头）
- [ ] 架构图（技术报告 Mermaid）截图备用
- [ ] 每段旁白卡在画面动作时长内，过场用快切不留白
- [ ] 总时长压在 **5:00 以内**（官方硬限制），建议留 10-15s 余量
- [ ] 旁白中文配音 + 英文字幕（或反之），术语出现时口语补一句
- [ ] 导出 1080p，存 `web/demo/madori-demo.mp4`（覆盖或新命名）
