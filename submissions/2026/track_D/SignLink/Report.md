# 指见咫尺(SignLink)项目架构设计说明书

> **项目愿景**：通过 AI 与实时音视频技术，打破听障人士与世界的沟通壁垒，构建一个集实时交流、情感表达与技能学习于一体的智能生态系统。

---

## 核心架构

### 1. 客户端 (Client - 移动端/端侧)
*   **UI/UX 交互层 (User Interface)**
    *   **开发框架**: `Flutter` (实现跨平台高性能渲染)
    *   **无障碍设计**: 高对比度配色、大尺寸交互组件、视觉震动反馈 (Haptic Feedback)
    *   **实时增强组件**: 
        *   `Text Overlay`: 实时翻译文字悬浮层
        *   `Emotive Particles`: 基于表情识别的情感粒子特效 (表情包)
*   **感知处理层 (Perception Engine)**
    *   **手部检测**: `MediaPipe Hands` (提取 21 个 3D 关键点)
    *   **面部检测**: `MediaPipe Face Mesh` (提取面部表情特征)
    *   **端侧推理**: `TensorFlow Lite` (运行轻量化手语识别模型)
*   **媒体引擎 (Media Engine)**
    *   **视频采集**: 高清摄像头流驱动
    *   **数据通道**: `WebRTC DataChannel` (用于同步传输识别出的文本数据)

### 2. 通信层 (Communication - 网络传输)
*   **协议栈 (Protocols)**
    *   `WebRTC (SRTP/DTLS)`: 实现加密、超低延迟的音视频流传输
    *   `WebSockets`: 用于房间建立、呼叫通知等信令 (Signaling) 交换
    *   `UDP`: 确保实时交互的极低延迟
*   **媒体服务器 (Media Server)**
    *   **架构模式**: `SFU (Selective Forwarding Unit)`
    *   **核心组件**: `Mediasoup` 或 `Janus` (负责多路视频流的高效转发，降低端侧能耗)

### 3. 后端与云端 (Backend - 逻辑与存储)
*   **业务微服务 (Microservices)**
    *   **开发语言**: `Go (Golang)` (处理高并发信令与逻辑)
    *   **功能模块**: 用户鉴权 (Auth)、房间管理 (Room Mgmt)、好友关系、通话状态管理
*   **数据存储层 (Data Storage)**
    *   **关系型数据库**: `PostgreSQL` (存储用户信息、个性化词库、学习记录)
    *   **高速缓存**: `Redis` (存储实时在线状态、通话信令缓存)
    *   **对象存储**: `AWS S3 / Google Cloud Storage` (存储教学视频、用户上传的素材)

### 4. AI 智能层 (AI Intelligence - 核心大脑)
*   **模型研发 (Model R&D)**
    *   **开发环境**: `Python` / `PyTorch`
    *   **模型架构**: `Transformer` 或 `LSTM` (处理手势动作的时序特征)
    *   **数据增强**: 针对坐标数据的平移、缩放、噪声增强算法
*   **推理策略 (Inference Strategy)**
    *   **端侧推理 (Edge)**: 负责快速、简单的日常词汇识别（低延迟）
    *   **云端推理 (Cloud)**: 负责复杂的长句语义理解与语法纠错（高精度）

---

##  产品核心模式 

| 模式名称 |  目标用户 |  核心技术重点 |  用户体验特征 |

 **纯手语模式 (Sign-to-Sign)** **:**  听障人士 --> 听障人士 | 极清视频流 + 情感表情包 | 追求极低延迟与极致画质，增强情感表达
 
**交流模式 (Sign-to-Text)** **:** 听障人士 --> 听人 | 手语识别 + 实时字幕 | 追求识别准确率与文字同步性 

 **学习模式 (Learning)** **:** 学习中的听障人士 | AI 动作纠错 + 间隔重复算法 | 强调反馈机制与个性化学习路径 

---

## 技术栈汇总 

*   **Frontend**: Flutter, Dart, MediaPipe, TFLite
*   **Backend**: Go, Microservices, gRPC
*   **Database**: PostgreSQL, Redis
*   **AI/ML**: Python, PyTorch, TensorFlow, MediaPipe
*   **Real-time**: WebRTC, Mediasoup, WebSocket
*   **Infrastructure**: Docker, Kubernetes, AWS/GCP