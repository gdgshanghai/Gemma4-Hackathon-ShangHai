// ── API 调用 ─────────────────────────────────────────
let _customUrl = '';
let _customKey = '';
let _customModel = '';

export function setCustomApi(url, key, model) { _customUrl = url; _customKey = key; _customModel = model || ''; }

function chatPayload(msg, provider, sid, mode) {
  const p = { message: msg, session_id: sid, provider, mode };
  if (provider && provider.startsWith('custom_') && _customUrl) {
    p.custom_url = _customUrl;
    p.custom_key = _customKey;
    p.custom_model = _customModel;
  }
  return JSON.stringify(p);
}

export async function apiChat(msg, provider, sid, mode) {
  const r = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: chatPayload(msg, provider, sid, mode),
  });
  return r.json();
}

/**
 * 流式聊天 — 通过 SSE 逐块读取回复
 * @param {string} msg
 * @param {string} provider
 * @param {string} sid
 * @param {string} mode
 * @param {function} onChunk - (text: string) => void
 * @param {function} onDone - (fullResponse: object) => void
 * @param {function} onError - (err: Error) => void
 */
export async function apiChatStream(msg, provider, sid, mode, onChunk, onDone, onError) {
  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: chatPayload(msg, provider, sid, mode),
    });
    if (!r.ok) {
      const errData = await r.json().catch(() => ({}));
      onError(new Error(errData.detail || `HTTP ${r.status}`));
      return;
    }
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const payload = line.slice(6).trim();
          if (!payload) continue;
          try {
            const evt = JSON.parse(payload);
            if (evt.type === 'chunk') {
              onChunk(evt.content || '');
            } else if (evt.type === 'result') {
              onDone(evt.data || {});
            }
          } catch { /* ignore parse errors */ }
        }
      }
    }
  } catch (e) {
    onError(e);
  }
}

export async function apiDeploy(wf, url, key) {
  const r = await fetch('/api/deploy', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ workflow: wf, n8n_url: url, n8n_api_key: key }),
  });
  return { ok: r.ok, data: await r.json() };
}

export async function apiExecute(wfId, n8nUrl, apiKey) {
  const r = await fetch('/api/execute-workflow', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ workflow_id: wfId, n8n_url: n8nUrl, n8n_api_key: apiKey }),
  });
  return { ok: r.ok, data: await r.json() };
}

export async function apiInfo() {
  try {
    const r = await fetch('/api/info');
    return await r.json();
  } catch { return { check_interval_min: 15 }; }
}

export async function apiHealth() {
  try {
    const r = await fetch('/api/health');
    const d = await r.json();
    return d.status === 'ok' ? 'online' : 'offline';
  } catch { return 'offline'; }
}

export async function apiProviderStatus() {
  try {
    const r = await fetch('/api/provider-status');
    return await r.json();
  } catch { return {}; }
}

export async function apiProviderLogs() {
  try {
    const r = await fetch('/api/provider-logs');
    return await r.json();
  } catch { return []; }
}

export async function apiDefaultInstances() {
  try {
    const r = await fetch('/api/default-instances');
    return await r.json();
  } catch { return []; }
}

export async function apiN8nHealth() {
  try {
    const r = await fetch('/api/n8n-health');
    return await r.json();
  } catch { return {}; }
}

export async function apiN8nLogs() {
  try {
    const r = await fetch('/api/n8n-logs');
    return await r.json();
  } catch { return []; }
}
