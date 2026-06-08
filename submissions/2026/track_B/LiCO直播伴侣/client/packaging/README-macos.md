# blivechat macOS 打包说明

与 Windows 版相同目标：**前端 + PyInstaller + 可选 OBS 插件 + 分发包**。  
**必须在 macOS 本机构建**（无法从 Windows 交叉编译 `.app`）。

## 环境要求

| 项目 | 说明 |
|------|------|
| 系统 | macOS 12+（Apple Silicon 或 Intel 各打各的包） |
| Python | 3.11+（`python3`） |
| Node.js | 18+（构建 Vue 前端） |
| 可选 | Homebrew：`ffmpeg`、`cmake`（编译 OBS 插件时需要） |
| OBS | 安装 [OBS Studio](https://obsproject.com/download)（编译插件时需要 SDK 路径） |

## 一键构建

```bash
cd packaging/scripts
chmod +x *.sh
./build-release.sh
```

产物：

| 文件 | 说明 |
|------|------|
| `packaging/dist/blivechat.app` | 主程序（双击或 `open dist/blivechat.app`） |
| `packaging/release/blivechat-<ver>-macos-<arch>.zip` | 分发压缩包 |
| `packaging/release/blivechat-<ver>-macos.dmg` | 可选 DMG（含 Applications 快捷方式） |

仅重建后端（前端已 build 过）：

```bash
./build-release.sh --skip-frontend
```

跳过 OBS 插件编译：

```bash
./build-release.sh --skip-plugin
```

## 配置与数据目录（与 Windows 不同）

| 项目 | 路径 |
|------|------|
| 配置 | `~/Library/Application Support/blivechat/data/config.ini` |
| 日志 | `~/Library/Application Support/blivechat/log/` |
| Qwen API | 同上 `[qwen]` 段，或环境变量 `DASHSCOPE_API_KEY` |

**不要**只改项目内 `data/config.ini`；打包后的 `.app` 不会读该路径。

## OBS 插件

将预编译的 `obs-blivechat-bridge.plugin` 放入 `packaging/vendor/`，构建时会复制进 `.app` 的 `vendor/`，`post-install.sh` 会安装到：

`~/Library/Application Support/obs-studio/plugins/`

手动编译插件：

```bash
./build-obs-plugin-macos.sh
```

## 安装后脚本

```bash
./post-install.sh "/path/to/blivechat.app"
```

## 与 Windows 版的差异

| 功能 | Windows | macOS（当前） |
|------|---------|----------------|
| 图形安装向导 (Inno Setup) | 有 | 无（ZIP/DMG + 手动拖到 Applications） |
| winget 自动装 FFmpeg/OBS | 有 | 提示 `brew install ffmpeg` |
| 数据目录 | `%ProgramData%\blivechat` | `~/Library/Application Support/blivechat` |
| OBS 插件格式 | `.dll` | `.plugin` bundle |

## 在 Windows 开发机上

无法在此生成 macOS `.app`。请使用 Mac 实机、Mac CI（GitHub Actions `macos-latest`）或远程 Mac 执行 `build-release.sh`。
