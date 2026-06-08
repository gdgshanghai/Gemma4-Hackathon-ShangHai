// ── 全局状态 ──────────────────────────────────────

export function loadInstances() {
  try { return JSON.parse(localStorage.getItem('n8n_instances') || '[]'); } catch { return []; }
}
export function saveInstances(list) {
  localStorage.setItem('n8n_instances', JSON.stringify(list));
}
export function upsertInstance(list, inst) {
  const idx = list.findIndex(i => i.id === inst.id);
  if (idx >= 0) { const u = [...list]; u[idx] = inst; return u; }
  return [...list, inst];
}
export function removeInstance(list, id) {
  return list.filter(i => i.id !== id);
}

// ── Provider 定义 ─────────────────────────────────
let _customIdCounter = 0;

const BUILTIN_PROVIDERS = [
  { id: 'openrouter_26b', group: '在线 API', type: 'cloud', key: 'openrouter_key_0', label: 'OpenRouter · Gemma 4 26B MoE', model: 'google/gemma-4-26b-a4b-it' },
  { id: 'openrouter_31b', group: '在线 API', type: 'cloud', key: 'openrouter_key_1', label: 'OpenRouter · Gemma 4 31B', model: 'google/gemma-4-31b-it' },
];

// 自定义 API（用户自部署的 Gemma 4，存 localStorage）
export function loadCustomProviders() {
  try { return JSON.parse(localStorage.getItem('custom_providers') || '[]'); } catch { return []; }
}
export function saveCustomProviders(list) {
  localStorage.setItem('custom_providers', JSON.stringify(list));
}
export function addCustomProvider(name, baseUrl, apiKey, modelName) {
  const list = loadCustomProviders();
  const id = 'custom_' + (++_customIdCounter) + '_' + Date.now().toString(36);
  list.push({ id, name, baseUrl: baseUrl.replace(/\/+$/, ''), apiKey, modelName: modelName || '', label: '🔌 ' + name });
  saveCustomProviders(list);
  return list;
}
export function removeCustomProvider(id) {
  const list = loadCustomProviders().filter(p => p.id !== id);
  saveCustomProviders(list);
  return list;
}

function getAllProviders() {
  const custom = loadCustomProviders().map(c => ({
    id: c.id,
    group: '自定义',
    type: 'custom',
    label: c.label || c.name,
    baseUrl: c.baseUrl,
    apiKey: c.apiKey,
    model: c.modelName || '',
  }));
  return [...BUILTIN_PROVIDERS, ...custom];
}

export function getProviders(onlineKeys = []) {
  return getAllProviders().filter(p => {
    if (p.type === 'cloud') {
      if (!p.key) return false;
      if (onlineKeys.length === 0) return true;
      return onlineKeys.includes(p.key);
    }
    return true; // 自定义 provider 始终显示
  });
}

export function getProviderById(id) {
  return getAllProviders().find(p => p.id === id);
}
