// 服务器连接配置。API_BASE 优先读 localStorage override（设置页可编辑），
// 否则回落到 Vite env（构建期注入），再缺省指向本地后端。
// WS_BASE 由 API_BASE 派生：http→ws / https→wss，复用同一 host:port。

// localStorage key（API base 运行时 override，见 SettingsDialog 服务器连接段「API 地址」）。
export const LS_API_BASE_KEY = "soundspeed.apiBase"

// localStorage key（admin token 持久化，见 SettingsDialog 服务器连接段）。
export const LS_TOKEN_KEY = "soundspeed.adminToken"

// 缺省后端地址（无 localStorage override 且无 VITE_API_BASE 时回落到此）。
// 无尾斜杠，SettingsDialog 保存时的「等于默认则 removeItem」比较直接用它。
export const DEFAULT_API_BASE = "http://localhost:8000"

// API base 在模块加载期定值（localStorage override 优先）。改地址必须整页 reload 才能在所有
// fetch/WS 生效（见 SettingsDialog 保存逻辑）。guard typeof localStorage，SSR/测试不炸。
function resolveApiBase(): string {
  const override =
    typeof localStorage !== "undefined" ? localStorage.getItem(LS_API_BASE_KEY) : null
  const base = (override?.trim() || import.meta.env.VITE_API_BASE) ?? DEFAULT_API_BASE
  return base.replace(/\/$/, "")
}

export const API_BASE = resolveApiBase()

// http→ws、https→wss 一并覆盖（正则只锚定开头的 http）。
export const WS_BASE = API_BASE.replace(/^http/, "ws")
