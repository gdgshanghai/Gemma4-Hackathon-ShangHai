# Project-Resurgence

[English](#english) | [中文](#中文)

---

## English

A Jetpack Compose Android application built with Kotlin. This project leverages Google's **Gemma 4** models through **LiteRT** (formerly TensorFlow Lite) for on-device intelligent capabilities, integrated alongside CameraX, Coil, OkHttp, and NanoHTTPD.

### Key Features
- **On-Device AI Engine**: Powered by LiteRT for local intelligence and real-time inference using Gemma 4.
- **Modern UI/UX**: Built entirely with Jetpack Compose following minimalist design principles.
- **Local Services**: Utilizes NanoHTTPD for embedded server capabilities and CameraX for fast image processing.

### Prerequisites

Before building the project, ensure you have installed the following tools:
- **Android Studio** Ladybug or newer
- **JDK 17** (Recommended for Gradle 8+) or **JDK 11**
- **Android SDK Platform** 36.1
- **Android SDK Build-Tools** 36.1.0
- An Android device or emulator running **Android 15 (API 35)** or newer

### Environment Setup

1. Install Android Studio.
2. Open **Settings / Preferences** and confirm the embedded JDK is set to JDK 17 (or compatible JDK 11+).
3. Open the project root in Android Studio.
4. Wait for the Gradle sync to finish and download all necessary dependencies.

> ⚠️ **Security Warning**: Do **NOT** commit your `key.properties` or keystore file (`.jks`) to the public repository. They have been added to `.gitignore` by default.

### `key.properties` Configuration (Optional for Release)

If you need to generate a signed release build, create a `key.properties` file in the project root:

```properties
storeFile=project-resurgence.jks
storePassword=your_store_password
keyAlias=your_key_alias
keyPassword=your_key_password
```
**Place the referenced keystore file in the project root, or update  to the correct relative path.storeFile**

## Build and Run
### Method 1: Via Android Studio (Recommended)
Select File > Sync Project with Gradle Files.
Wait until the dependency download completes.
Choose the app module run configuration.
Click Run (Green Play Button) to install the app on your connected device or emulator.

### Method 2: Via Command Line (CLI)
For Linux/macOS:
```
./gradlew assembleDebug
./gradlew installDebug
```
For Windows PowerShell:
```
.\gradlew.bat assembleDebug
.\gradlew.bat installDebug
```
## Build Release APK
If key.properties is properly configured, run:
Linux/macOS: 
```
./gradlew assembleRelease
```
Windows: 
```
.\gradlew.bat assembleRelease
```
## Technical Notes
Target SDK: API 36.1
Min SDK: API 35 (Android 15)
Permissions: Requires Camera permissions for vision-related features.
## Troubleshooting
Gradle Sync Fails: Confirm that Android Studio has downloaded the exact Android SDK Platform 36.1 and Build-Tools via SDK Manager.
App Won't Install: Verify that your physical device or emulator is running Android 15 (API 35) or above.

---
## 中文
基于 Kotlin 和 Jetpack Compose 开发的 Android 应用程序。本项目作为 GDG Gemma 4 Hackathon 参赛作品，通过 LiteRT（原 TensorFlow Lite）在端侧集成了 Google Gemma 4 大模型能力，并结合了 CameraX、Coil、OkHttp 和 NanoHTTPD 组件。

## 核心亮点
端侧 AI 引擎：基于 LiteRT 构建，实现 Gemma 4 模型的高效本地离线推理与智能交互。
现代化 UI：全量使用 Jetpack Compose 构建，遵循现代极简视觉与动效设计。
本地微服务：集成 NanoHTTPD 嵌入式服务器，结合 CameraX 打造流畅的图像处理流水线。

## 开发前准备
在构建项目之前，请确保本地已安装并配置以下工具：
Android Studio Ladybug 或更高版本
JDK 17（推荐，支持现代 Gradle 构建）或 JDK 11
Android SDK Platform 36.1
Android SDK Build-Tools 36.1.0
一台运行 Android 15 (API 35) 或更高版本的安卓真机或模拟器

## 环境搭建
安装并打开 Android Studio。
进入 Settings / Preferences，确保内置 JDK 设置为 JDK 17 或兼容的 JDK 11 版本。
在 Android Studio 中打开项目根目录。
等待 Gradle 自动同步完成并下载所有核心依赖项。

**⚠️ 安全警告：请切勿将您的 key.properties 或签名密钥文件（.jks）提交到公开代码仓库中。项目已默认将它们列入 .gitignore。**

## key.properties 签名配置（Release 可选）
如果您需要打包经过签名的 Release 版本，请在项目根目录下创建 key.properties 文件
Properties 文件内容如下：
storeFile=project-resurgence.jks
storePassword=你的密钥库密码
keyAlias=你的别名
keyPassword=你的密钥密码
并将对应的 .jks 文件放入项目根目录，或在 storeFile 中填写正确的相对路径。

## 编译与运行
### 方法一：通过 Android Studio 运行（推荐）
点击菜单栏 File > Sync Project with Gradle Files 进行配置同步。
等待构建索引和依赖下载完毕。
选择 app 模块的运行配置。
点击 Run 按钮（绿色三角）将应用安装至连接的真机或模拟器。

### 方法二：通过命令行运行
Linux / macOS 用户：
```
./gradlew assembleDebug
./gradlew installDebug
```
Windows PowerShell 用户：
```
.\gradlew.bat assembleDebug
.\gradlew.bat installDebug
```
## 构建 Release 正式包
在配置好 key.properties 后，执行以下命令进行打包：
Linux/macOS: 
```
./gradlew assembleRelease
```
Windows: 
```
.\gradlew.bat assembleRelease
```

## 项目技术说明
目标架构 (Target SDK): API 36.1
最低支持 (Min SDK): API 35 (Android 15)
权限说明: 部分 AI 视觉相关功能依赖相机（Camera）权限。

## 常见问题排查
Gradle 同步失败：请检查 Android Studio 的 SDK Manager，确保完整下载了 Android SDK Platform 36.1 及其对应的构建工具。
应用无法安装：请检查当前连接的测试设备或模拟器系统版本是否达到了 Android 15 (API 35) 的最低要求。