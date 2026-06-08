# 智能盆栽

- 赛道：Track C / Edge AI
- 队伍：The Weeknd
- 项目：智能盆栽
- 模型：`gemma-4-E2B-it-GGUF`

## 提交说明

## 目录结构

```text
Gemma4_TrackC_Submission/
├─ APP/                     Flutter 端侧应用
├─ firmware/                ESP32-S3 固件
├─ TECH_REPORT.md           技术报告
└─ .gitignore               忽略本地隐私配置与构建产物
```

## 项目概述

本项目是一个基于 Gemma 4 的端侧智能盆栽系统：

- 手机端使用 Flutter 构建交互界面。
- 端侧大模型通过 `llamadart` 加载本地 GGUF 模型，当前提交版本实际使用 `gemma-4-E2B-it-GGUF`。
- 多模态识别通过图片输入 + 文本提示完成植物识别与人格化生成。
- ESP32-S3 负责采集土壤湿度、温度、PIR、摄像头等硬件数据，并通过本地 Web API 与 App 联动。

## Gemma 4 使用方式

- 实际使用规格：`gemma-4-E2B-it-GGUF`。
- 使用原因：该版本更符合本项目当前的端侧部署与多模态实验方案，能够兼顾本地运行、视觉识别接入。
- 调用方式：
  - 文本对话：本地 GGUF 模型加载与流式生成。
  - 多模态识别：图片 + 文本共同送入本地模型。
  - 记忆压缩：使用本地模型对历史互动进行总结，降低上下文占用。

## 硬件环境

- 主控：ESP32-S3-DevKitC-1
- 摄像头：GC0308 / 8225N v2.0
- 显示屏：ST7735 / ST7789 系列
- 传感器：
  - 土壤湿度传感器
  - 温度传感器（DallasTemperature / OneWire）
  - PIR 人体红外传感器

## 软件环境

- Windows 10/11
- Flutter 3.x
- Dart 3.x
- Android Studio 或已配置 Android SDK 的 Flutter 环境
- PlatformIO Core
- Python 3.x

## 复现步骤

### 1. 准备 Gemma 4 模型

请自行准备 Gemma 4 的本地 GGUF 模型文件。

- 纯文本模式：准备 `gemma-4-E2B-it-GGUF` 对应 GGUF 文件。
- 多模态模式：除 GGUF 外，还需准备对应的 `mmproj` 文件。
- 推荐将文件放在 Android 设备的 `Download` 目录下。

### 2. 运行 APP

进入 `APP/` 目录后执行：

```bash
flutter pub get
flutter run
```

首次启动后，请在应用配置页手动填写：

- 本地 GGUF 模型路径
- 多模态 mmproj 路径
- 硬件 IP 地址
- 硬件端口

本提交包默认不写入任何 API Key、Wi-Fi、局域网地址或个人私有配置。

### 3. 配置并烧录固件

进入 `firmware/src/` 目录：

1. 将 `wifi_credentials.example.h` 复制为 `wifi_credentials.h`
2. 按你的现场网络填写 Wi-Fi 名称与密码

示例：

```cpp
#define WIFI_CREDENTIALS \
    {"YourWiFi", "YourPassword"} \
    /*, {"BackupWiFi", "BackupPassword"} */
```

然后进入 `firmware/` 目录执行：

```bash
pio run
pio run --target upload
pio device monitor
```

说明：

- `platformio.ini` 中没有写死任何作者机器专用路径、串口号或密码。
- 评委可根据自己设备情况填写 `upload_port` / `monitor_port`。

## 隐私与安全处理

本提交包已做如下脱敏：

- 删除硬编码 Wi-Fi 账号与密码
- 删除硬编码串口号与本地构建目录
- 删除默认局域网 IP 与 API Key
- 删除依赖外网的摄像头占位图回退逻辑

同时通过 `.gitignore` 忽略：

- `firmware/src/wifi_credentials.h`
- Flutter 与 PlatformIO 构建缓存

## 核心代码位置

- App 入口：`APP/lib/main.dart`
- Gemma 4 本地推理：`APP/lib/services/local_llama_service.dart`
- 多模态植物识别：`APP/lib/services/plant_recognition_service.dart`
- 记忆压缩：`APP/lib/providers/memory_provider.dart`
- 硬件通信：`APP/lib/services/planter_service.dart`
- 固件入口：`firmware/src/main.cpp`
- Wi-Fi 配置与时间同步：`firmware/src/wifi_time.cpp`
- Web API：`firmware/src/web_server.cpp`

## 评审建议操作路径

建议评委按以下路径快速体验：

1. 烧录 `firmware/` 固件并配置本地 Wi-Fi
2. 在 Android 设备安装运行 `APP/`
3. 在配置页填写 Gemma 4 模型路径与硬件 IP
4. 进入拍照识别页面，测试植物识别与人格生成
5. 进入聊天页面，测试端侧对话与记忆能力
6. 进入状态页，观察 App 与 ESP32-S3 的传感器联动

## 说明

- 本仓库不直接附带 Gemma 4 大模型权重文件，评委需按比赛要求自行放置本地模型。
- 为减小提交体积，本提交包未附带 ONNX 语音模型文件，保留的核心能力为离线文本对话、离线多模态识别和硬件联动。
- 联网主要用于局域网内 App 与硬件通信，以及可选的 NTP 校时。
