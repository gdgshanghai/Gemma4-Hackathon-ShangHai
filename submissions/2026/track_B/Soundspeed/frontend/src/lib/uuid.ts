// 全局唯一 id 生成。优先 crypto.randomUUID（仅 HTTPS / localhost 等安全源可用）；
// 局域网 HTTP（iPad/手机经 LAN IP 访问，见 spec §3.5）下 crypto.randomUUID 为 undefined，
// 直接调用会抛 TypeError，故回退到带前缀的时间戳+随机串（仅需唯一，不要求密码学强度）。
export function randomId(fallbackPrefix: string): string {
  return crypto?.randomUUID?.() ?? `${fallbackPrefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`
}
