# APK 构建说明

本文件用于指导审核团队从 `Gemma4_TrackC_Submission/APP` 目录直接构建安卓 APK。

## 1. 环境要求

请确保评委机器已安装以下环境：

- Flutter SDK
- Android SDK
- Java 17 或兼容版本
- 可用的 Android 构建工具链

建议先执行：

```bash
flutter doctor
```

确认 Flutter 与 Android 环境正常。

## 2. 构建步骤

进入 `APP/` 目录：

```bash
cd APP
```

安装依赖：

```bash
flutter pub get
```

构建 Release APK：

```bash
flutter build apk --release
```

## 3. APK 输出位置

构建完成后，APK 默认输出到：

```text
APP/build/app/outputs/flutter-apk/app-release.apk
```

## 4. 首次运行后的必要配置

由于本提交包已去除所有隐私与现场相关配置，首次启动 App 后，请在应用配置页手动填写：

- 本地 `gemma-4-E2B-it-GGUF` 模型路径
- 多模态 mmproj 路径
- 硬件 IP 地址
- 硬件端口

说明：

- 本仓库不内置 `gemma-4-E2B-it-GGUF` 大模型权重文件。
- 如需体验多模态植物识别，必须准备对应的视觉投影器 `mmproj` 文件。
- 为减少提交体积，本提交包未包含 ONNX 语音模型文件，也未保留语音播报入口。

## 5. 关于复现

### 仅构建 APK

如果评委只验证“是否能成功打包安卓应用”，那么执行本文件中的构建命令即可。

### 完整功能复现

如果评委希望体验完整赛道 C 功能，还需要：

1. 在 Android 设备中放置 `gemma-4-E2B-it-GGUF` 本地模型文件
2. 按 `README.md` 配置并烧录 `firmware/`
3. 在 App 配置页填写模型与硬件信息

说明：

- 当前 `submission` 已删除 ONNX 语音模型文件，并移除了语音播报入口。
- 因此“完整功能复现”指的是 Gemma 4 端侧对话、多模态植物识别、记忆能力与 ESP32-S3 硬件联动。
- 语音播报不属于本提交包的复现范围。

## 6. 说明

- `submission` 中已经包含构建 APK 所需的核心 Flutter 工程文件。
- 被忽略的 `.iml`、`.kotlin`、`.dart_tool`、`build/` 等文件均为可自动生成文件，不影响 APK 构建。
- 若遇到依赖下载问题，请检查 Flutter 镜像、Gradle 网络和 Android SDK 配置。
