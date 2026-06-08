#!/usr/bin/env bash
# 局域网 HTTPS 一键配置（每台 Mac 各自跑一次）。
#
# 自动探测本机 .local 主机名 → mkcert 生成证书 → 写 frontend/.env.production
# → 从 Caddyfile.template 渲染本机 ./Caddyfile。
#
# 前置：brew install mkcert caddy
# 跑法：从仓库任意位置  ./scripts/setup-https.sh
#
# 生成的 certs/ ./Caddyfile frontend/.env.production 都被 gitignore，是本机相关值，不入库。

set -euo pipefail

# 切到仓库根（脚本可从任意 cwd 调用）
cd "$(git rev-parse --show-toplevel)"

# --- 1. 探测本机 .local 主机名 + 端口 ---
# LocalHostName 是 Bonjour/mDNS 名，无空格；为空时退回 hostname -s。
HOSTBASE="$(scutil --get LocalHostName 2>/dev/null || true)"
[ -z "$HOSTBASE" ] && HOSTBASE="$(hostname -s)"
SITE="${HOSTBASE}.local"
# 用 8443 高端口：免 sudo。443 是特权端口，每次启动都要 root 密码，对“各自跑一份”太烦。
# 代价仅是 URL 多个 :8443。想用 443 把这里改成 443、启动命令前加 sudo 即可。
HTTPS_PORT=8443
ENTRY="https://${SITE}:${HTTPS_PORT}"
echo "▶ 本机入口：${ENTRY}"

# --- 2. 依赖检查 ---
for bin in mkcert caddy; do
	if ! command -v "$bin" >/dev/null 2>&1; then
		echo "✗ 缺 $bin。先跑：brew install mkcert caddy" >&2
		exit 1
	fi
done

# --- 3. mkcert 本地 CA ---
# -install 把 CA 装进系统信任库，需要密码；只为本机浏览器自测，手机信任不依赖它。
# 非致命：装不上也能继续（证书生成只要 CAROOT 存在）。
echo "▶ 确保 mkcert 本地 CA（可能要密码，跳过也不影响手机）"
mkcert -install || echo "  （跳过系统信任，手机仍可经 rootCA 信任）"

# --- 4. 生成证书（SAN 只含 .local + localhost，抗 DHCP，无机器相关 IP）---
# 注：SAN 是主机名级，与端口无关，不含 :8443。
echo "▶ 生成证书到 ./certs"
mkdir -p certs
mkcert -cert-file certs/soundspeed.pem -key-file certs/soundspeed-key.pem \
	"$SITE" localhost 127.0.0.1

# --- 5. 前端生产构建配置 ---
echo "▶ 写 frontend/.env.production"
cat > frontend/.env.production <<EOF
# 由 scripts/setup-https.sh 生成（gitignore）。指向本机 Caddy HTTPS 入口。
# 本机 dev（pnpm dev）仍走 .env 的 http://localhost:8000，互不影响。
VITE_API_BASE=${ENTRY}
EOF

# --- 6. 渲染本机 Caddyfile（{{SITE}} 注入「主机名:端口」）---
echo "▶ 渲染 ./Caddyfile（gitignore）"
sed -e "s/{{SITE}}/${SITE}/g" -e "s/{{HTTPS_PORT}}/${HTTPS_PORT}/g" Caddyfile.template > Caddyfile

# --- 7. 校验 ---
caddy validate --config ./Caddyfile >/dev/null 2>&1 \
	&& echo "✓ Caddyfile 校验通过" \
	|| { echo "✗ Caddyfile 校验失败" >&2; exit 1; }

CAROOT="$(mkcert -CAROOT)"
cat <<EOF

✅ 配置完成（本机入口：${ENTRY}）

下一步：
  1. 构建前端：  cd frontend && pnpm install && pnpm build && cd ..
  2. 起后端：    PORT=8000 SOUNDSPEED_DEV=1 python -m backend.api
  3. 起 Caddy：  caddy run --config ./Caddyfile          # 8443 免 sudo
  4. 手机同 Wi-Fi 开：${ENTRY}/admin   （在「服务器连接」手填 token：devtoken）

手机信任本机 CA（不做则 wss 连不上）：
  把这个文件传到各自手机安装：
    ${CAROOT}/rootCA.pem
  iOS：装描述文件后，去 设置>通用>关于本机>证书信任设置 打开「完全信任」
  Android：设置>安全>加密与凭据>安装证书>CA 证书

注意：每台 Mac 的 mkcert 根 CA 各不相同，不能共用。每个人都要把
自己机器的 rootCA.pem 装到要访问它的手机上。
EOF
