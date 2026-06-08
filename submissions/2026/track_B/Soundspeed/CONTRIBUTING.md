# 协作约定

## 分支

- `main` 永远保持可跑、可演示，不直接在上面改。
- 每个功能拉独立分支，命名 `<type>/<描述>`：
  - `feat/` 新功能 · `fix/` 修 bug · `spike/` 实验 · `docs/` 文档 · `chore/` 杂项
- 实验代码走 `spike/` 分支或 `scripts/`，不污染 `main`。

## 工作流程

```sh
# 1. 从最新 main 拉分支
git checkout main && git pull --rebase origin main
git checkout -b feat/asr-streaming

# 2. 开发，小步提交（提交信息带前缀）
git add <files> && git commit -m "feat: ..."

# 3. 推送
git push -u origin feat/asr-streaming

# 4. GitHub 开 PR（base: main），队友 review

# 5. Squash and merge，删远端分支

# 6. 收尾
git checkout main && git pull --rebase origin main
git branch -d feat/asr-streaming
```

## 分支落后了

```sh
git checkout main && git pull --rebase origin main
git checkout <你的分支> && git rebase main
# 解冲突后 git rebase --continue
git push --force-with-lease
```

## 规则

- PR 控制在 10 分钟能看完的大小，小步快跑。
- 队友几小时不在又卡 deadline，可自行合并，但合进 `main` 必须能跑。
- 每天一次简短同步：今天我动哪些文件，避免撞车。
- 提交信息前缀 `feat / fix / docs / chore`，方便回溯、写技术报告。
- 模块边界（ASR 输出、take 信号、Gemma tool schema、SQLite 表结构）先在 `docs/` 钉死，再并行开发。
- 里程碑打 tag：`mvp` / `p2` / `p3`。
