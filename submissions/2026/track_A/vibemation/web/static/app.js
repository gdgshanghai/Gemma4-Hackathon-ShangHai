// ── 主应用 (Preact + HTM) ──────────────────────────
import { html, render, useState, useEffect, marked } from './preact.js';
import { apiChat, apiChatStream, setCustomApi, apiHealth, apiInfo, apiDefaultInstances, apiProviderStatus, apiProviderLogs, apiN8nHealth, apiN8nLogs, apiDeploy, apiExecute } from './api.js';
import { loadInstances, saveInstances, getProviderById, getProviders, removeInstance, addCustomProvider, removeCustomProvider } from './store.js';
import InstanceManager from './components/InstanceManager.js';
import WorkflowCard from './components/WorkflowCard.js';
import { showToast } from './toast.js';
import { FrontendAgent, frontendDeploy, frontendExecute } from './frontend-agent.js';

const sessionId = 's' + Date.now();

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [provider, setProvider] = useState('openrouter_26b');
  const [mode, setMode] = useState('workflow');
  const [health, setHealth] = useState('checking');
  const [onlineKeys, setOnlineKeys] = useState([]);
  const [instances, setInstances] = useState(loadInstances);
  const [currentInstance, setCurrentInstance] = useState(null);
  const [checkInterval, setCheckInterval] = useState(15000);
  const [showCustomForm, setShowCustomForm] = useState(false);
  const [customName, setCustomName] = useState('');
  const [customUrl, setCustomUrl] = useState('');
  const [customKey, setCustomKey] = useState('');
  const [customModel, setCustomModel] = useState('');
  const [logs, setLogs] = useState([]);
  const [showLogs, setShowLogs] = useState(false);
  const [configTab, setConfigTab] = useState('api');
  const [n8nHealth, setN8nHealth] = useState({});
  const [n8nLogs, setN8nLogs] = useState([]);
  const [frontendMode, setFrontendMode] = useState(false);
  const frontendAgent = useState(() => new FrontendAgent())[0];

  const prov = getProviderById(provider);

  // 读取后端配置 + 健康检查
  useEffect(() => {
    apiInfo().then(info => {
      setCheckInterval((info.check_interval_min || 15) * 60 * 1000);
    });
    const check = async () => {
      const h = await apiHealth();
      setHealth(h);
      if (h === 'online') {
        const raw = await apiProviderStatus();
        const status = raw.results || raw; // 兼容新旧格式
        setOnlineKeys(Object.entries(status).filter(([, v]) => v).map(([k]) => k));
        loadDefaults();
      }
    };
    check();
    const t = setInterval(check, 15000);
    // n8n 保活: 14 分钟检查一次
    const n8nTimer = setInterval(() => {
      apiN8nHealth().then(setN8nHealth);
      apiN8nLogs().then(setN8nLogs);
    }, 14 * 60 * 1000);
    return () => { clearInterval(t); clearInterval(n8nTimer); };
  }, []);

  // 可用 providers（过滤掉离线的 cloud）
  const availableProviders = getProviders(onlineKeys);

  const loadDefaults = async () => {
    const defaults = await apiDefaultInstances();
    if (!defaults.length) return;
    const existing = loadInstances();
    let changed = false;
    defaults.forEach(d => {
      if (localStorage.getItem('hide_builtin_' + d.url)) return;
      if (!existing.find(i => i.url === d.url)) {
        existing.push({ id: 'def-' + Date.now().toString(36) + Math.random().toString(36).slice(2, 4), ...d });
        changed = true;
      }
    });
    if (changed) { saveInstances(existing); setInstances(existing); }
  };

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    setMessages(m => [...m, { role: 'user', content: text }]);

    if (frontendMode && prov?.type === 'custom' && prov?.baseUrl) {
      // 前端模式：直接调用自定义 API
      setLoading(true);
      try {
        const result = await frontendAgent.run(text, prov.baseUrl, prov.apiKey || '', prov.model || '');
        const next = [{ role: 'assistant', content: result.content || '' }];
        if (result.toolCalls?.length) {
          result.toolCalls.forEach(tc => next.push({ role: 'tool', content: '🛠 ' + tc.name + '\n' + JSON.stringify(tc.arguments, null, 2) }));
        }
        if (result.workflow) next.push({ role: 'workflow', workflow: result.workflow });
        setMessages(m => [...m, ...next]);
      } catch (e) {
        setMessages(m => [...m, { role: 'assistant', content: '❌ 请求失败: ' + e.message }]);
      }
      setLoading(false);
      return;
    }

    if (mode === 'chat') {
      // 流式聊天
      setLoading(true);
      const assistantIdx = Date.now();
      setMessages(m => [...m, { role: 'assistant', content: '', _idx: assistantIdx }]);
      apiChatStream(text, provider, sessionId, mode,
        // onChunk
        (chunk) => {
          setMessages(m => m.map(msg =>
            msg._idx === assistantIdx
              ? { ...msg, content: msg.content + chunk }
              : msg
          ));
        },
        // onDone
        () => { setLoading(false); },
        // onError
        (err) => {
          setMessages(m => m.map(msg =>
            msg._idx === assistantIdx
              ? { ...msg, content: '❌ ' + err.message }
              : msg
          ));
          setLoading(false);
        }
      );
      return;
    }

    setLoading(true);
    try {
      const data = await apiChat(text, provider, sessionId, mode);
      const next = [{ role: 'assistant', content: data.content || '' }];
      if (data.tool_calls) data.tool_calls.forEach(tc => next.push({ role: 'tool', content: '🛠 ' + tc.name + '\n' + JSON.stringify(tc.arguments, null, 2) }));
      if (data.workflow) next.push({ role: 'workflow', workflow: data.workflow });
      setMessages(m => [...m, ...next]);
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', content: '❌ 请求失败: ' + e.message }]);
    }
    setLoading(false);
  };

  const clearChat = () => setMessages([]);

  const loadLogs = async () => {
    const data = await apiProviderLogs();
    setLogs(data.reverse());
  };

  const toggleLogs = () => {
    if (!showLogs) { loadLogs(); apiN8nHealth().then(setN8nHealth); apiN8nLogs().then(setN8nLogs); }
    setShowLogs(!showLogs);
    setConfigTab('api');
  };

  const hideBuiltin = (url) => {
    localStorage.setItem('hide_builtin_' + url, '1');
    setInstances(instances.filter(i => i.url !== url));
  };

  const healthDot = health === 'online' ? 'green' : health === 'offline' ? 'red' : 'yellow';
  const healthText = health === 'online' ? 'API 已就绪' : health === 'offline' ? '部分离线' : '检查中...';
  const modelBadge = prov?.label || provider;
  const placeholder = '描述工作流...';
  const EXAMPLES = [
    '创建一个 Manual Trigger 工作流，用 Code 节点计算 1 到 100 的和并返回结果',
    '创建一个 Webhook 工作流，收到 POST 请求后把 body 原样返回（echo 服务）',
    '创建一个 Manual Trigger 工作流，用 HTTP Request 节点查询 https://httpbin.org/get 并返回',
  ];

  const fillExample = (text) => { setInput(text); };
  // 点击示例时填入输入框（同时通过 DOM 操作确保立即反映）
  const fillExampleDirect = (text) => {
    setInput(text);
    const el = document.querySelector('input[placeholder*="工作流"], input[placeholder*="说点什么"]');
    if (el) {
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      nativeSetter.call(el, text);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }
  };
  if (typeof window !== 'undefined') window.__fillExample = fillExampleDirect;

  // 模拟长对话（三屏，含超大工作流触发滚动）
  const simulate = () => {
    const convos = [
      '创建一个 webhook 接收 GitHub push 事件，然后发送飞书通知',
      '在 webhook 后面加一个 IF 节点，只过滤 main 分支',
      '在 IF 节点的 false 分支上加一个 Slack 通知',
      '帮我写一个 HTTP 请求节点，调用百度翻译 API',
      '把第一个节点的超时时间改为 30 秒',
      '添加一个 Code 节点，把返回数据转换成大写',
      '在最后加一个 Merge 节点，合并所有分支',
      '创建一个定时触发器，每天早上 9 点运行',
      '添加一个 Switch 节点，按 status 字段分流',
      '在每条分支末尾加一个飞书通知',
    ];
    const replies = [
      '已创建 webhook + 飞书通知工作流，包含 2 个节点。',
      '已添加 IF 节点，条件: $json.branch === "main"。',
      'false 分支已添加 Slack 通知节点。',
      '已添加 HTTP Request 节点，URL: https://api.baidu.com/translate。',
      '第一个 webhook 节点的超时时间已更新为 30 秒。',
      '已添加 Code 节点，脚本: return data.map(d => ({...d, text: d.text?.toUpperCase()}));',
      'Merge 节点已添加，模式: combine。',
      '已添加 Schedule Trigger，CRON: 0 9 * * *。',
      '已添加 Switch 节点，按 $json.status 分流。',
      '各分支末尾已添加飞书通知节点。',
    ];
    // 超大工作流 JSON（20+ 节点，超出 max-height 触发滚动）
    const bigWorkflow = {
      name: '完整自动化流水线',
      nodes: Array.from({ length: 22 }, (_, i) => ({
        name: 'Node_' + (i + 1),
        type: ['n8n-nodes-base.webhook', 'n8n-nodes-base.if', 'n8n-nodes-base.httpRequest',
               'n8n-nodes-base.code', 'n8n-nodes-base.slack', 'n8n-nodes-base.feishu',
               'n8n-nodes-base.set', 'n8n-nodes-base.switch', 'n8n-nodes-base.merge',
               'n8n-nodes-base.splitInBatches', 'n8n-nodes-base.github', 'n8n-nodes-base.cron'][i % 12],
        typeVersion: 1,
        position: [i * 200, 0],
        parameters: { operation: 'execute', timeout: 30, retries: 3 },
      })),
      connections: Object.fromEntries(
        Array.from({ length: 21 }, (_, i) => [i, { main: [[{ node: 'Node_' + (i + 2), outputIndex: 0 }]] }])
      ),
    };

    const msgs = [];
    // 10 轮 = 约 3 屏
    convos.forEach((d, i) => {
      msgs.push({ role: 'user', content: d });
      msgs.push({ role: 'assistant', content: replies[i] });
      if (i === convos.length - 1) {
        // 最后一轮加超大工作流
        msgs.push({ role: 'workflow', workflow: bigWorkflow });
      } else if (i % 3 === 2) {
        msgs.push({ role: 'workflow', workflow: { name: '工作流 ' + (i + 1), nodes: [{ name: 'Trigger' }, { name: 'Action' }, { name: 'Output' }], connections: {} } });
      }
    });
    setMessages(msgs);
  };

  return html`
    <div class="sidebar">
      <div>
        <h1 style="display:flex;align-items:center;justify-content:space-between">
          n8n Agent
          <label style="display:flex;align-items:center;gap:4px;font-size:11px;cursor:pointer;color:#9ca3af;font-weight:400;text-transform:none;letter-spacing:0">
            <input type="checkbox" checked=${frontendMode} onChange=${(e) => setFrontendMode(e.target.checked)}
              style="width:14px;height:14px;cursor:pointer" />
            前端模式
          </label>
        </h1>
        <div class="sub">基于 Gemma 4 原生函数调用生成 n8n 工作流</div>
      </div>
      <div>
        <label>推理后端</label>
        <select value=${provider} onChange=${(e) => {
          const id = e.target.value;
          setProvider(id);
          const p = getProviderById(id);
          if (p && p.baseUrl) setCustomApi(p.baseUrl, p.apiKey || '', p.model || '');
        }}>
          ${availableProviders.map(p => html`<option value=${p.id}>${p.label}</option>`)}
        </select>
      </div>
      <div>
        <label>模式</label>
          <label class="toggle">
            <input type="checkbox" checked=${mode === 'workflow'}
              onChange=${(e) => setMode(e.target.checked ? 'workflow' : 'chat')} />
            <span class="toggle-slider"></span>
            <span class="toggle-label">${mode === 'workflow' ? '🔧 工作流' : '💬 对话'}</span>
          </label>
        </div>
      <div style="margin-bottom:8px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
          <label>自部署 API</label>
          <button class="btn btn-primary btn-sm" onClick=${() => { setCustomName(''); setCustomUrl('https://'); setCustomKey(''); setCustomModel(''); setShowCustomForm(true); }}>+</button>
        </div>
      </div>

      ${showCustomForm ? html`
        <div style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:2000;display:flex;align-items:center;justify-content:center"
             onClick=${(e) => { if (e.target === e.currentTarget) setShowCustomForm(false); }}>
          <div style="background:#1a1f2e;border-radius:14px;padding:24px;width:90%;max-width:420px;box-shadow:0 20px 60px rgba(0,0,0,.5);color:#e4e7eb"
               onClick=${(e) => e.stopPropagation()}>
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
              <span style="font-size:18px;font-weight:700">🔌 添加自定义 API</span>
              <span style="cursor:pointer;font-size:20px;color:#6b7280" onClick=${() => setShowCustomForm(false)}>✕</span>
            </div>
            <div style="display:flex;flex-direction:column;gap:12px">
              <input placeholder="名称（如 我的 GPU 服务器）" value=${customName}
                onInput=${(e) => setCustomName(e.target.value)}
                style="padding:10px 12px;border:1px solid #374151;border-radius:8px;background:#0f1419;color:#e4e7eb;font-size:14px;outline:none" />
              <input placeholder="API 地址（https://your-api.com/v1）" value=${customUrl}
                onInput=${(e) => setCustomUrl(e.target.value)}
                style="padding:10px 12px;border:1px solid #374151;border-radius:8px;background:#0f1419;color:#e4e7eb;font-size:14px;outline:none" />
              <input type="password" placeholder="API Key（可选）" value=${customKey}
                onInput=${(e) => setCustomKey(e.target.value)}
                style="padding:10px 12px;border:1px solid #374151;border-radius:8px;background:#0f1419;color:#e4e7eb;font-size:14px;outline:none" />
              <input placeholder="模型名称（如 google/gemma-4-26b-it，可选）" value=${customModel}
                onInput=${(e) => setCustomModel(e.target.value)}
                style="padding:10px 12px;border:1px solid #374151;border-radius:8px;background:#0f1419;color:#e4e7eb;font-size:14px;outline:none" />
            </div>
            <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:20px">
              <button onClick=${() => setShowCustomForm(false)}
                style="padding:10px 20px;border:1px solid #374151;border-radius:8px;background:transparent;color:#9ca3af;cursor:pointer;font-size:14px">取消</button>
              <button onClick=${() => {
                if (!customName || !customUrl) return;
                addCustomProvider(customName, customUrl, customKey, customModel);
                setCustomName(''); setCustomUrl(''); setCustomKey(''); setCustomModel('');
                setShowCustomForm(false);
                // 选中刚添加的自定义 provider
                const list = JSON.parse(localStorage.getItem('custom_providers') || '[]');
                if (list.length) setProvider(list[list.length-1].id);
              }}
                style="padding:10px 20px;border:none;border-radius:8px;background:${!customName || !customUrl ? '#374151' : '#3b82f6'};color:#fff;cursor:${!customName || !customUrl ? 'not-allowed' : 'pointer'};font-size:14px">添加</button>
            </div>
          </div>
        </div>
      ` : ''}
      <${InstanceManager} instances=${instances} setInstances=${setInstances}
        currentInstance=${currentInstance} setCurrentInstance=${setCurrentInstance} />
      <div style="margin-top:auto;display:flex;gap:6px">
        <button onClick=${toggleLogs} style="flex:1;padding:8px;border:1px solid #2d3748;border-radius:6px;background:transparent;color:#9ca3af;cursor:pointer;font-size:13px">
          ⚙️ 配置
        </button>
      </div>
    </div>

    <div class="main">
      <div class="chat">
        ${messages.map(msg => {
          if (msg.role === 'workflow') return html`<${WorkflowCard} workflow=${msg.workflow} instance=${currentInstance} frontendMode=${frontendMode} />`;
          const htmlContent = msg.role === 'user' ? msg.content.replace(/\n/g, '<br>') : marked.parse(msg.content || '');
          return html`<div class="msg ${msg.role} md" innerHTML=${htmlContent} />`;
        })}
      </div>

      <div class="examples-row">
        ${EXAMPLES.map(ex => html`
          <button onClick=${() => fillExampleDirect(ex)} class="example-chip" title=${ex}>💡 ${ex.slice(0, 25)}${ex.length > 25 ? '...' : ''}</button>
        `)}
      </div>

      <div class="input-bar">
        <input type="text" placeholder=${placeholder} value=${input}
               onInput=${(e) => setInput(e.target.value)}
               onKeyDown=${(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }} />
        <button onClick=${simulate} style="background:#6b7280;font-size:11px">🎬 模拟</button>
        <button onClick=${clearChat} style="background:#9ca3af">清空</button>
        <button onClick=${send} disabled=${loading}>${loading ? '思考中...' : '发送'}</button>
      </div>

      <div class="status">
        <span class="dot ${healthDot}"></span>
        <span>${healthText}</span>
        <span style="margin-left:auto;color:#999">${currentInstance?.name || ''}</span>
        <span class="model-badge">${modelBadge}</span>
      </div>
    </div>

    ${showLogs ? html`
      <div style="position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:1000;display:flex;align-items:center;justify-content:center"
           onClick=${(e) => { if (e.target === e.currentTarget) setShowLogs(false); }}>
        <div style="background:#0f1419;color:#e4e7eb;border-radius:12px;width:90%;max-width:720px;height:80vh;display:flex;box-shadow:0 20px 60px rgba(0,0,0,.5)">
          <!-- 左侧导航 -->
          <div style="width:160px;border-right:1px solid #2d3748;padding:16px 0;display:flex;flex-direction:column;gap:2px">
            ${[
              { id: 'api', label: '📡 API 连通性' },
              { id: 'n8n', label: '🔗 n8n 实例' },
            ].map(tab => html`
              <div onClick=${() => setConfigTab(tab.id)}
                style="padding:10px 16px;cursor:pointer;font-size:14px;${configTab === tab.id ? 'background:rgba(59,130,246,.15);color:#3b82f6;border-right:2px solid #3b82f6' : 'color:#9ca3af'}">
                ${tab.label}
              </div>
            `)}
          </div>
          <!-- 右侧内容 -->
          <div style="flex:1;display:flex;flex-direction:column;min-width:0">
            <div style="display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid #2d3748">
              <span style="font-size:16px;font-weight:600">${configTab === 'api' ? '📡 API 连通性' : '🔗 n8n 实例'}</span>
              <span style="cursor:pointer;font-size:20px;color:#6b7280" onClick=${() => setShowLogs(false)}>✕</span>
            </div>

            ${configTab === 'api' ? html`
              <!-- API 连通性 -->
              <div style="flex:1;overflow-y:auto;padding:16px 20px;font-size:14px;font-family:monospace">
                <div style="margin-bottom:12px;padding:10px;background:rgba(59,130,246,.1);border-radius:8px;font-size:13px;font-family:sans-serif">
                  <div style="color:#9ca3af;margin-bottom:8px">检测间隔: ${checkInterval / 60000}-${checkInterval / 60000 + 1} 分钟随机</div>
                  <div style="display:flex;gap:12px;flex-wrap:wrap">
                    <span style="padding:4px 10px;border-radius:4px;font-size:13px;
                      background:${onlineKeys.filter(k => k.startsWith('openrouter')).length > 0 ? 'rgba(34,197,94,.15)' : 'rgba(239,68,68,.15)'};
                      color:${onlineKeys.filter(k => k.startsWith('openrouter')).length > 0 ? '#22c55e' : '#ef4444'}">
                      OpenRouter (${onlineKeys.filter(k => k.startsWith('openrouter')).length}/3)
                    </span>
                    <span style="padding:4px 10px;border-radius:4px;font-size:13px;
                      background:${onlineKeys.includes('nvidia') ? 'rgba(34,197,94,.15)' : 'rgba(239,68,68,.15)'};
                      color:${onlineKeys.includes('nvidia') ? '#22c55e' : '#ef4444'}">
                      NVIDIA (${onlineKeys.includes('nvidia') ? 1 : 0}/1)
                    </span>
                  </div>
                </div>
                ${logs.length === 0 ? html`<div style="color:#6b7280;text-align:center;padding:20px">暂无记录</div>` : ''}
                ${logs.map(log => html`
                  <div style="padding:8px 0;border-bottom:1px solid #1f2937">
                    <div style="color:#6b7280;font-size:12px;margin-bottom:4px">${new Date(log.time * 1000).toLocaleString()}</div>
                    ${Object.entries(log.results).map(([k, v]) => html`
                      <span style="display:inline-block;margin:2px 4px 2px 0;padding:2px 8px;border-radius:4px;font-size:12px;
                        background:${v ? 'rgba(34,197,94,.15)' : 'rgba(239,68,68,.15)'};
                        color:${v ? '#22c55e' : '#ef4444'}">${k}: ${v ? '✅' : '❌'}</span>
                    `)}
                  </div>
                `)}
              </div>
              <div style="padding:10px 20px;border-top:1px solid #2d3748;font-size:12px;color:#6b7280;text-align:center">
                <span style="cursor:pointer;color:#3b82f6" onClick=${() => { loadLogs(); }}>🔄 刷新</span>
              </div>
            ` : html`
              <!-- n8n 实例管理（含隐藏的） -->
              <div style="flex:1;overflow-y:auto;padding:16px 20px;font-size:14px">
                <div style="display:flex;gap:8px;margin-bottom:12px">
                  <button onClick=${() => apiN8nHealth().then(setN8nHealth)} style="padding:6px 14px;border:1px solid #2d3748;border-radius:6px;background:transparent;color:#9ca3af;cursor:pointer;font-size:12px">🔄 检测连通性</button>
                </div>
                ${(() => {
                  // 所有已保存的实例 + 内建实例（含隐藏的）
                  const all = [...instances];
                  const builtins = [{name:'Render 测试版',url:'https://n8n-server-fepr.onrender.com',builtin:true}];
                  builtins.forEach(b => { if (!all.find(i => i.url === b.url)) all.push(b); });
                  return all.map(inst => {
                    const hidden = localStorage.getItem('hide_builtin_' + inst.url) === '1';
                    return html`
                      <div style="display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:8px;margin-bottom:6px;background:rgba(255,255,255,.04);${hidden ? 'opacity:.4' : ''}">
                        <span style="font-size:16px">${n8nHealth[inst.url] === true ? '🟢' : n8nHealth[inst.url] === false ? '🔴' : '⚪'}</span>
                        <span style="flex:1;font-weight:500">${inst.name}</span>
                        <span style="font-size:12px;color:#6b7280">${inst.builtin ? 'builtin' : ''}</span>
                        <span style="font-size:12px;color:#6b7280;max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${inst.url}</span>
                        <button onClick=${() => {
                          if (hidden) { localStorage.removeItem('hide_builtin_' + inst.url); window.location.reload(); }
                          else { localStorage.setItem('hide_builtin_' + inst.url, '1'); setInstances(instances.filter(i => i.id !== inst.id)); }
                        }} style="padding:4px 10px;border:1px solid ${hidden ? '#22c55e' : '#6b7280'};border-radius:4px;background:transparent;color:${hidden ? '#22c55e' : '#9ca3af'};cursor:pointer;font-size:12px">
                          ${hidden ? '显示' : '隐藏'}
                        </button>
                        ${!inst.builtin ? html`
                          <button onClick=${() => { if (confirm('删除?')) setInstances(removeInstance(instances, inst.id)); }} style="padding:4px 10px;border:1px solid #ef4444;border-radius:4px;background:transparent;color:#ef4444;cursor:pointer;font-size:12px">删除</button>
                        ` : ''}
                      </div>
                    `;
                  });
                })()}
              </div>
              <!-- n8n 请求日志 -->
              <div style="border-top:1px solid #2d3748;padding:12px 20px">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
                  <span style="font-size:13px;color:#9ca3af">请求记录</span>
                  <span style="cursor:pointer;color:#3b82f6;font-size:12px" onClick=${() => apiN8nLogs().then(setN8nLogs)}>🔄 刷新</span>
                </div>
                <div style="max-height:150px;overflow-y:auto;font-size:12px;font-family:monospace">
                  ${n8nLogs.length === 0 ? html`<div style="color:#6b7280;text-align:center;padding:8px">暂无记录</div>` : ''}
                  ${n8nLogs.map(log => html`
                    <div style="display:flex;gap:8px;padding:4px 0;border-bottom:1px solid #1f2937">
                      <span style="color:#6b7280;flex-shrink:0">${new Date(log.time * 1000).toLocaleTimeString()}</span>
                      <span style="color:${log.ok ? '#22c55e' : '#ef4444'};flex-shrink:0">${log.ok ? '✅' : '❌'}</span>
                      <span style="color:#9ca3af;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${log.url}</span>
                      <span style="color:#6b7280">${log.status || log.error?.slice(0,30) || ''}</span>
                    </div>
                  `)}
                </div>
              </div>
            `}
          </div>
        </div>
      </div>
    ` : ''}
  `;
}

render(html`<${App} />`, document.getElementById('app'));
