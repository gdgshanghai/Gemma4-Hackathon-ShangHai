# 局域网 HTTPS：让手机访问并发语音 / 图片 / 文件

2026-06-07。给手机经同 Wi-Fi 访问本机 Soundspeed admin，能录语音 note、传图片/文件。

## 为什么要 HTTPS

只有**语音**逼着上 HTTPS。手机录音走 `getUserMedia`（`useVoiceRecorder.ts`、`useMicLevel.ts`），
浏览器只在 secure context（HTTPS 或 localhost）下放行麦克风；手机用局域网 IP 走 HTTP 不是 secure
context，麦克风直接被禁。图片/文件走普通 `<input type=file>`，HTTP 就能传，HTTPS 只是顺带覆盖。

连锁约束：前端页面一旦 HTTPS，就不能再发 HTTP / `ws://`（mixed content 被拦）。前端 WS 从
`VITE_API_BASE` 派生（`config.ts`：http→ws / https→wss），所以**后端也得在 HTTPS 后面**。

方案：Caddy 在高端口（默认 8443，免 sudo）做唯一 HTTPS 终止点，前后端两个 HTTP 服务原封不动，同源转发。前后端代码零改动。

## 每台 Mac 各自配（这是 B 场景：每个人在自己 Mac 上各跑一份 server）

机器相关的只有三样：主机名、证书、构建配置。`scripts/setup-https.sh` 自动搞定，跑一次即可：

```bash
brew install mkcert caddy          # 一次性
./scripts/setup-https.sh           # 探测本机 .local 主机名 → 生成证书 → 写 .env.production → 渲染 Caddyfile
```

脚本生成的三样东西都被 gitignore（本机值，不入库）：

- `certs/`：mkcert 证书，SAN 含本机 `.local` 主机名（如 `macbook-pro-1370.local`）
- `frontend/.env.production`：`VITE_API_BASE=https://<本机>.local`
- `Caddyfile`：从 `Caddyfile.template` 渲染，填入本机主机名

仓库里跟踪的只有 `Caddyfile.template` 和 `scripts/setup-https.sh`，跨机器通用。换机器重跑脚本即可。

## 每次启动

```bash
cd frontend && pnpm install && pnpm build && cd ..   # 给手机用的产物，必须 build 不是 dev
PORT=8000 SOUNDSPEED_DEV=1 python -m backend.api      # 后端，监听 0.0.0.0:8000
caddy run --config ./Caddyfile                       # 8443，免 sudo
# 手机同 Wi-Fi 开 https://<本机>.local:8443/admin
```

**别让手机连 `pnpm dev`**：那是 PR #55 白屏 OOM 的元凶（React19 dev 的 PerformanceMeasure 泄漏
×60fps 重渲），现场跑 dev 直接崩标签页。手机只连 build 产物。

## 手机信任本机 mkcert 根 CA（不做则 wss 握手失败）

`wss://` 在手机 Safari 上没有「仍要访问」的旁路，证书不受信直接连不上。

```bash
open "$(mkcert -CAROOT)"            # 里面的 rootCA.pem 传到手机
```

**iOS**：AirDrop / 邮件 `rootCA.pem` 到 iPhone → 点开 → 设置 > 通用 > VPN与设备管理 里装这个
描述文件 → **还要**去 设置 > 通用 > 关于本机 > 证书信任设置，把 mkcert 那条打开「完全信任」。
第二步最容易漏，漏了照样连不上。

**Android**：传 `rootCA.pem` 到手机 → 设置 > 安全 > 加密与凭据 > 安装证书 > CA 证书。

**每台 Mac 的 mkcert 根 CA 各不相同，没法共享**。每个人都要把自己机器的 `rootCA.pem` 装到要访问
它的手机上。（技术上可以全队共用一个 CAROOT，但那要分发 CA 私钥，安全风险，不推荐。）

## 两个会卡住的坑

1. **手机要手填 token**。生产 build 不自动填 devtoken（只 dev 构建自动填），手机进 /admin 后在
   「服务器连接」里手填 `devtoken` 才连得上 WS，否则 401。
2. **统一用 `.local` 主机名访问**，别用 IP。`VITE_API_BASE` 钉死了 hostname，混用 IP 会变跨源
   （CORS 是 `*` 能跑通，但容易自己绕晕）。SAN 也只签 `.local`，不含 IP，抗 DHCP 漂移。
