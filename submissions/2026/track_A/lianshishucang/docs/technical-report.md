# 链识数藏 — 技术报告

## 一、模型选型理由

### 1.1 选型背景

链识数藏的核心流程之一是**实物收藏品 AI 识别**：用户拍摄实物（手办、卡牌、模型等）上传后，系统需自动识别其名称、系列、材质、尺寸、市场估值及风格标签。这要求模型具备**多模态视觉理解能力**，同时兼顾推理精度、响应速度、部署成本与数据隐私。

在 2025 年可选的多模态模型中，主要候选包括：

| 模型 | 优势 | 劣势 |
|------|------|------|
| GPT-4V | 视觉理解能力强 | API 成本高、数据需传输至 OpenAI |
| Claude 3 Sonnet/Opus | 中文支持好 | 成本较高、无本地部署方案 |
| LLaVA / CogVLM | 开源可自部署 | 精度不及商业模型、硬件需求高 |
| **Gemma 4** | **Google 出品、多规格可选、支持本地部署** | 社区生态较新 |

综合考虑后选定 **Google Gemma 4** 作为核心视觉推理模型。

### 1.2 为何选择 Gemma 4

选择 Gemma 4 而非上述竞品，基于以下关键考量：

1. **规格灵活，按场景选型** — Gemma 4 提供从轻量级（e4b）到全量（31B）的多规格版本，可根据部署环境（云端推理 vs 本地运行）灵活切换，这是 GPT-4V 和 Claude 3 无法提供的。
2. **多模态原生能力** — Gemma 4 系列原生支持图像+文本的多模态输入，无需额外的视觉编码器桥接，推理管线更简洁。
3. **Google 基础设施背书** — 可通过 Google AI Studio / Gemini API 直接调用，延迟和可用性有保障。
4. **开源可用，支持私有化部署** — Gemma 4 权重开源，可通过 LM Studio 等工具在本地运行，满足数据隐私要求高的场景。
5. **成本优势** — 在同等精度水平下，Gemma 4 的 API 调用成本显著低于 GPT-4V 和 Claude 3。

### 1.3 三个规格的选择理由

系统实际配置了三套 Gemma 4 规格，形成**多级降级策略**：

| 规格 | 环境变量默认值 | 托管平台 | 用途 |
|------|--------------|----------|------|
| `gemma-4-multimodal` | `GEMMA_MODEL` | Google AI Studio (Gemini API) | **主推理引擎**，精度最高 |
| `google/gemma-4-31b-it:free` | `OPENROUTER_MODEL` | OpenRouter / Cloudflare AI Gateway | **免费备选**，同等架构 |
| `google/gemma-4-e4b` | `LM_STUDIO_MODEL` | LM Studio（本地） | **本地兜底**，隐私优先 |

#### `gemma-4-multimodal`（主引擎）

- **平台**：Google AI Studio / Gemini API
- **选型理由**：这是 Google 官方托管的 Gemma 4 全功能版本，推理精度最高，对实物照片中的细节（材质纹理、标识文字、造型特征）辨识能力最强。作为首要推理路径，适用于绝大多数用户上传场景。
- **折衷**：需要网络请求，存在一定延迟（200-800ms），数据需传输至 Google 服务器。

#### `google/gemma-4-31b-it:free`（免费备选）

- **平台**：OpenRouter / Cloudflare AI Gateway
- **选型理由**：OpenRouter 上提供了 Gemma 4 31B 指令微调版本的免费额度（`:free` 后缀），与 Google 官方版本同属 31B 参数规格，推理质量基本一致。通过 Cloudflare AI Gateway 可进一步优化大陆地区的访问速度。当主引擎配额耗尽或不可用时自动切换。
- **折衷**：免费额度有速率限制，不适合高频生产环境。

#### `google/gemma-4-e4b`（本地兜底）

- **平台**：LM Studio（localhost:1234）
- **选型理由**：Gemma 4 e4b（4B 参数）是系列中最轻量的版本，可在消费级 GPU 甚至纯 CPU 环境下运行。适用于以下场景：
  - **数据隐私优先**：收藏品照片可能包含用户个人空间信息，本地推理避免数据外传。
  - **离线环境**：内网部署或无互联网访问时的备用方案。
  - **开发调试**：本地快速迭代，无需依赖外部 API。
- **折衷**：4B 参数在复杂藏品识别上精度低于 31B 版本，偶有属性提取不完整的情况。

### 1.4 模型选型决策树

```
用户上传照片
    │
    ├─→ GEMMA_PROVIDER 是否指定？
    │     ├─ yes → 使用指定提供商的对应规格
    │     └─ no  → 依次尝试：
    │           ├─ (1) Google AI Studio → gemma-4-multimodal
    │           ├─ (2) OpenRouter      → google/gemma-4-31b-it:free
    │           └─ (3) LM Studio       → google/gemma-4-e4b
    │
    └─→ 全部失败 → 返回错误，提示用户重试
```

每一级均包含指数退避重试逻辑，单级失败后自动进入下一级，最大限度提升识别成功率。

---

## 二、架构设计

### 2.1 系统总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (React + TypeScript)              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Inventory │  │  Upload  │  │  Wallet  │  │  Market  │    │
│  │   Grid    │  │  Panel   │  │  Connect │  │  Panel   │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│                       ↕ HTTP / WebSocket                    │
├─────────────────────────────────────────────────────────────┤
│                  后端 (Go + Gin Framework)                    │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────────┐    │
│  │  Routes  │→│ Handlers │→│      Services           │    │
│  │          │  │          │  │  ┌──────────────────┐  │    │
│  │  /api/*  │  │  Auth    │  │  │ GemmaService     │  │    │
│  │          │  │  NFT     │  │  │   ├─ Google AI   │  │    │
│  │          │  │  Collect │  │  │   ├─ OpenRouter  │  │    │
│  │          │  │  AIGC    │  │  │   └─ LM Studio   │  │    │
│  │          │  │  Web3    │  │  │  AIGCService     │  │    │
│  │          │  │  Market  │  │  │  Compositing     │  │    │
│  │          │  │          │  │  │  IPFSService     │  │    │
│  │          │  │          │  │  │  Blockchain      │  │    │
│  │          │  │          │  │  │  EventListener   │  │    │
│  │          │  │          │  │  └──────────────────┘  │    │
│  └──────────┘  └──────────┘  └────────────────────────┘    │
│                       ↕ GORM                                │
│              ┌────────────────────────┐                     │
│              │     PostgreSQL         │                     │
│              │  (8 张表, AutoMigrate)  │                    │
│              └────────────────────────┘                     │
├─────────────────────────────────────────────────────────────┤
│          区块链层 (Ethereum Sepolia / Hardhat Local)          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │LianShiNFT  │  │Marketplace │  │  Auction   │            │
│  │ (ERC-721)  │  │(FixedPrice)│  │  (Timed)   │            │
│  └────────────┘  └────────────┘  └────────────┘            │
│                       ↕ go-ethereum RPC                     │
│              ┌────────────────────────┐                     │
│              │     Event Listener     │                     │
│              │  (轮询 MINT/LIST/SOLD)  │                    │
│              └────────────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 后端分层架构

后端采用经典的四层架构：

```
Routes ──→ Handlers ──→ Services ──→ Models
  │            │             │            │
  │ 路由注册    │ 请求校验     │ 业务逻辑    │ 数据建模
  │ 中间件      │ 响应组装     │ 外部调用    │ GORM 映射
```

- **Routes** (`routes/routes.go`) — 全局路由注册，区分公开 API 和 JWT 保护 API；应用 CORS、认证中间件。
- **Handlers** — 请求入口，负责参数解析、校验和响应组装，不包含业务逻辑。
- **Services** — 业务逻辑核心，封装 AI 调用、图像处理、IPFS 上传、区块链交互等复杂操作。
- **Models** — GORM 模型定义，包含 8 张表的映射关系和状态常量。

### 2.3 AI 服务多层降级设计

`GemmaService` 实现了三提供商自动降级，核心设计要点：

```
type GemmaService struct {
    providers []GemmaProvider  // 有序提供商列表
}

func (s *GemmaService) AnalyzeImage(imageData string) (*CollectibleAttributes, error) {
    var lastErr error
    for _, provider := range s.providers {  // 按序尝试
        for retry := 0; retry < maxRetries; retry++ {
            result, err := provider.Analyze(imageData)
            if err == nil {
                return result, nil
            }
            lastErr = err
            time.Sleep(backoff(retry))  // 指数退避
        }
    }
    return nil, lastErr
}
```

- **有序列表**：`[GoogleAIProvider, OpenRouterProvider, LMStudioProvider]`
- **指数退避**：重试间隔呈指数增长，避免短时间内重复请求压垮服务
- **JSON 解析容错**：提供商返回的原始响应通过规范化处理后，使用 `strictjson` 解析，失败时尝试容错解析（如截取第一个 `{}` 块）
- **系统提示词强约束**：通过 `gemmaSystemPrompt` 强制要求模型仅输出固定 JSON Schema，减少解析失败概率

### 2.4 核心数据流：实物 → NFT

```
 ┌───────┐    ┌──────────┐    ┌────────┐    ┌──────┐    ┌─────┐    ┌──────────┐    ┌───────┐
 │ 用户   │    │ Collection│    │ Gemma  │    │ AIGC │    │ IPFS │    │ MetaMask │    │ Chain │
 │ 上传   │───→│ Handler   │───→│Service │───→│Service│───→│Service│───→│ 签名交易  │───→│ Event │
 │ 照片   │    │ (202 ACC) │    │ 识别    │    │ 制卡  │    │ 上传  │    │ 铸造    │    │ 监听  │
 └───────┘    └──────────┘    └────────┘    └──────┘    └─────┘    └──────────┘    └───────┘
                   │               │            │           │            │              │
                   │               │            │           │            │              │
              status:          status:      status:     status:      status:        status:
              PENDING_AI       STORED       CARD_READY   AWAITING     MINTED         MINTED
                                                        _MINT
```

完整状态流转：

```
PENDING_AI → STORED → CARD_READY → AWAITING_MINT → MINTED
     ↑           ↑          ↑            ↑
  上传完成     AI 识别    AIGC 制卡     IPFS 上传
              完成        完成          完成
```

**关键设计决策**：AI 识别和 AIGC 制卡均采用**异步处理**模式。Upload API 立即返回 `202 Accepted`，后台 goroutine 异步执行耗时操作，前端通过轮询状态字段获取进度。这样避免了 HTTP 长连接占用，提升了 API 吞吐量。

### 2.5 智能合约架构

三合约设计，职责分离：

```
LianShiNFT (ERC-721)
├── ERC721URIStorage — 元数据上链
├── ERC2981 — 版税支持（最高 10%）
├── 铸造逻辑 — 记录 minter 与 creator
└── 元数据更新 — Token URI 管理

LianShiMarketplace
├── 固定价格挂单 — list / buy / cancel
├── Offer 出价 — makeOffer / acceptOffer
├── 平台手续费 — 可配置百分比
├── 版税分配 — 调用 ERC2981
└── ReentrancyGuard — 防重入

LianShiAuction
├── 限时拍卖 — startAuction / placeBid / settleAuction
├── 保留价与最低加价 — reservePrice / minBidIncrement
├── 竞拍者退款 — outbid 时自动退回首付款
└── 拍卖取消 — 仅无出价时可取消
```

**设计要点**：
- **分离 Auction 和 Marketplace**：拍卖逻辑较复杂（时间管理、退款、结算），与固定价格市场分离可降低单合约复杂度，也便于各自独立升级。
- **接口隔离**：`ILianShiNFT` 和 `ILianShiNFTForAuction` 分离，Marketplace 只能调用 NFT 的必要查询接口，Auction 合约额外需要 `safeTransferFrom` 权限。
- **版税标准化**：采用 ERC-2981 标准，Marketplace 和 Auction 在结算时均调用 `royaltyInfo` 自动分配版税。
- **防重入**：关键函数使用 `ReentrancyGuard`，避免跨合约调用时的重入攻击。

### 2.6 事件驱动架构

`EventListener` 以固定间隔轮询区块链上的合约事件：

```
Event Listener (goroutine 轮询)
    │
    ├─ LianShiNFT
    │   └─ NFTMinted(tokenId, creator, minter, tokenURI)
    │       └─ 更新 NFT 表中 minted 状态，关联 PhysicalCollection
    │
    ├─ LianShiMarketplace
    │   ├─ ListingCreated(listingId, tokenId, price)
    │   ├─ ItemSold(listingId, buyer, totalPrice)
    │   └─ ListingCancelled(listingId)
    │       └─ 同步 Listing 表状态
    │
    └─ LianShiAuction
        ├─ AuctionCreated(auctionId, tokenId, reservePrice)
        ├─ BidPlaced(auctionId, bidder, amount)
        ├─ AuctionSettled(auctionId, winner, amount)
        └─ AuctionCancelled(auctionId)
            └─ 同步 Auction 表状态
```

**设计理由**：将链上状态同步到关系数据库，使得前后端查询时无需每次都调用 RPC 节点，显著降低延迟和 RPC 费用。同时数据库支持复杂查询（按用户、状态、时间筛选），链上事件日志仅作为最终一致性保障。

### 2.7 前端架构

```
Frontend (React 18 + TypeScript + Vite)
│
├── 组件层 (components/inventory/)
│   ├── InventoryPage — 页面根组件
│   ├── InventoryGrid — 收藏品网格展示
│   ├── InventoryDetailPanel — 单品详情与编辑
│   ├── InventoryUploadPanel — 上传与 AI 识别
│   ├── InventoryMarketPanel — 市场操作
│   ├── InventoryToolbar — 搜索与筛选
│   └── ...（约 22 个组件）
│
├── 逻辑层 (lib/)
│   ├── inventory/ — 数据获取、状态管理
│   │   ├── useInventoryData.ts — 库存状态 Hook
│   │   ├── useInventoryMarketData.ts — 市场数据 Hook
│   │   └── adapters.ts — 后端 → 前端数据适配
│   ├── web3/ — 区块链交互
│   │   ├── useWallet.ts — 钱包连接 (viem)
│   │   ├── useContractWrite.ts — 合约写入抽象
│   │   ├── config.ts — 链配置与合约地址
│   │   └── abi.ts — ABI 定义
│   ├── api/ — HTTP 客户端
│   ├── i18n/ — 国际化 (zh/en)
│   └── ... 
│
└── 数据层
    ├── demo mode — 本地 Mock 数据 (inventoryDemoData.ts)
    └── live mode — 后端 API 调用 + 区块链直接交互
```

**关键设计决策**：
- **双模式（Demo / Live）**：前端通过 JWT 是否存在自动切换模式。Demo 模式使用本地 Mock 数据，方便 UI 开发和展示；Live 模式连接真实后端和链。
- **Hook 封装**：将 API 调用、状态管理、Demo/Live 切换封装在自定义 Hook 中，组件层无需关心数据来源。
- **i18n 优先**：内置中英文国际化，默认中文，适应目标用户群体。
- **viem 替代 ethers**：viem 是 TypeScript 原生 Web3 库，类型安全更好，Tree-shaking 更优，适合现代 React 项目。

---

## 三、总结

| 维度 | 选型结论 | 理由 |
|------|---------|------|
| 视觉模型 | Gemma 4（三规格降级） | 精度达标、成本可控、可本地部署 |
| 后端框架 | Go + Gin | 高性能、并发模型适合 AI 编排场景 |
| 数据库 | PostgreSQL | 结构化数据 + JSONB 灵活属性存储 |
| 智能合约 | Solidity 0.8.20 + OZ | 成熟生态，安全审计保障 |
| 合约部署 | Hardhat + Foundry | Hardhat 部署脚本成熟，Foundry 测试速度更快 |
| 前端框架 | React 18 + Vite + TypeScript | 组件生态丰富，类型安全 |
| Web3 前端 | viem | TypeScript 原生，轻量 |
| 钱包认证 | EIP-191 + JWT | 去中心化身份验证，无密码方案 |
| 元数据存储 | IPFS (Pinata) | 去中心化存储，符合 NFT 标准 |
| AI 网关 | 三级降级 + 指数退避 | 高可用，单点故障不影响核心流程 |
