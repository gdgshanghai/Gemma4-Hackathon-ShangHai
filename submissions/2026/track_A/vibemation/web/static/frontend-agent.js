/**
 * 前端 Agent — 浏览器端运行 n8n 工作流生成逻辑
 *
 * 替代后端 agent/ 模块，直接在前端调用 LLM API + 解析工具调用 + 管理记忆。
 *
 * 使用场景:
 *   前端模式开启时，用户的自定义 API / n8n 实例都由前端直连。
 *   内置 provider（OpenRouter）因 Key 在后端，仍走后端。
 */

/* ── 工具定义（同 agent/tools.py） ─────────────── */
const N8N_TOOLS = [
  {
    type: 'function',
    function: {
      name: 'generate_n8n_workflow',
      description: '根据用户需求生成可执行的 n8n 工作流 JSON',
      parameters: {
        type: 'object',
        properties: {
          name: { type: 'string', description: '工作流名称' },
          nodes: { type: 'array', items: { type: 'object' }, description: 'n8n 节点列表' },
          connections: { type: 'object', description: '节点连接关系' },
        },
        required: ['name', 'nodes', 'connections'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'modify_n8n_workflow',
      description: '修改已有的 n8n 工作流（增删节点或调整连接）',
      parameters: {
        type: 'object',
        properties: {
          operation: { type: 'string', enum: ['add_node', 'remove_node', 'update_node', 'reconnect'] },
          target_node: { type: 'string', description: '目标节点名称或索引' },
          changes: { type: 'object', description: '修改内容' },
        },
        required: ['operation', 'target_node', 'changes'],
      },
    },
  },
];

/* ── 对话记忆 ──────────────────────────────── */
class ConversationMemory {
  constructor() {
    this.history = [];
    this.workflowState = null;
  }
  addMessage(role, content, toolCalls) {
    const msg = { role };
    if (content) msg.content = content;
    if (toolCalls) msg.tool_calls = toolCalls;
    this.history.push(msg);
  }
  addToolResult(name, result) {
    this.history.push({
      role: 'tool',
      name,
      content: typeof result === 'string' ? result : JSON.stringify(result),
    });
  }
  updateWorkflow(wf) { this.workflowState = wf; }
  getContext() {
    const ctx = [...this.history];
    if (this.workflowState) {
      ctx.unshift({
        role: 'system',
        content: `当前工作流状态:\n${JSON.stringify(this.workflowState, null, 2)}\n\n基于此状态进行修改。`,
      });
    }
    return ctx;
  }
  clear() { this.history = []; this.workflowState = null; }
}

/* ── Gemma 4 内联格式解析 ────────────────────── */
function _extractBraces(text, start) {
  let depth = 0, i = start;
  while (i < text.length) {
    if (text[i] === '{') depth++;
    else if (text[i] === '}') { depth--; if (depth === 0) return [text.slice(start, i + 1), i + 1]; }
    i++;
  }
  return [text.slice(start), text.length];
}

function parseToolCalls(content) {
  const calls = [];
  const re = /<\|?tool_call\|\>?call:(\w+)(.*?)<\|?tool_call\|\>?/gs;
  let m;
  while ((m = re.exec(content)) !== null) {
    const name = m[1];
    const raw = m[2].trim();
    const braceStart = raw.indexOf('{');
    if (braceStart >= 0) {
      try {
        const [jsonStr] = _extractBraces(raw, braceStart);
        calls.push({ name, arguments: JSON.parse(jsonStr) });
      } catch { /* skip parse errors */ }
    }
  }
  return calls;
}

/* ── 前端 Agent ───────────────────────────── */
export class FrontendAgent {
  constructor() {
    this.memory = new ConversationMemory();
    this.systemPrompt =
      '你是 n8n 工作流生成助手。使用提供的工具生成、修改和验证 n8n 工作流 JSON。' +
      '每次生成工作流时，请确保节点位置合理（每列间隔 200px），连接关系正确。' +
      '支持多轮对话逐步构建复杂工作流。' +
      '重要：每次回复时，先用自然语言简要说明你生成的或修改的内容，再调用工具。' +
      '不要只输出工具调用而不说话。';
  }

  async run(userInput, apiUrl, apiKey, modelName) {
    this.memory.addMessage('user', userInput);
    const toolHint = '\n\n可用工具:\n' + N8N_TOOLS.map(t => `- ${t.function.name}: ${t.function.description}`).join('\n') +
      '\n\n调用格式: <|tool_call|>call:函数名{"参数名": "参数值"}<|tool_call|>';
    const messages = [
      { role: 'system', content: this.systemPrompt + toolHint },
      ...this.memory.getContext(),
    ];

    // 直接调用自定义 API
    const resp = await fetch(apiUrl + '/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}) },
      body: JSON.stringify({ model: modelName || 'gpt-3.5-turbo', messages, tools: N8N_TOOLS, temperature: 0 }),
    });
    if (!resp.ok) throw new Error(`API ${resp.status}: ${await resp.text()}`);
    const data = await resp.json();
    const msg = data.choices?.[0]?.message || {};
    const result = { content: msg.content || '', toolCalls: [], workflow: null };

    // 解析 tool_calls
    let rawCalls = msg.tool_calls || [];
    if (!rawCalls.length && msg.content) {
      rawCalls = parseToolCalls(msg.content);
      result.content = msg.content.replace(/<\|?tool_call\|\>?call:\w+.*?<\|?tool_call\|\>?/gs, '').trim();
    }

    for (const tc of rawCalls) {
      const name = tc.function?.name || tc.name;
      const args = tc.function?.arguments ? JSON.parse(tc.function.arguments) : (tc.arguments || {});
      if (name === 'generate_n8n_workflow') {
        const wf = { name: args.name || 'untitled', nodes: args.nodes || [], connections: args.connections || {}, settings: {}, version: 2 };
        this.memory.updateWorkflow(wf);
        result.workflow = wf;
      } else if (name === 'modify_n8n_workflow' && this.memory.workflowState) {
        const current = this.memory.workflowState;
        if (args.operation === 'add_node' && current.nodes?.length) {
          args.changes.position = [current.nodes[current.nodes.length - 1].position[0] + 200, current.nodes[current.nodes.length - 1].position[1]];
          current.nodes.push(args.changes);
          this.memory.updateWorkflow(current);
          result.workflow = current;
        }
      }
      result.toolCalls.push({ name, arguments: args });
      this.memory.addToolResult(name, { status: 'ok' });
    }
    this.memory.addMessage('assistant', msg.content, msg.tool_calls);

    // content 为空时补说明
    if (!result.content && result.workflow) {
      const names = result.workflow.nodes.map(n => n.name).join(' → ');
      result.content = `已生成工作流「${result.workflow.name}」，包含 ${result.workflow.nodes.length} 个节点：${names}`;
    }
    return result;
  }

  reset() { this.memory.clear(); }
}

/* ── n8n 前端直连 ─────────────────────────── */
export async function frontendDeploy(wf, n8nUrl, apiKey) {
  // 转换 connections 格式 + 添加 Webhook 触发器 + 激活
  const nodes = [...(wf.nodes || [])];
  const webhookPath = addWebhookTrigger(nodes, wf.connections || {});
  const converted = convertConnections(nodes, wf.connections || {});
  const payload = { name: wf.name, nodes, connections: converted, settings: wf.settings || {} };

  const r = await fetch(`${n8nUrl.replace(/\/+$/, '')}/api/v1/workflows`, {
    method: 'POST',
    headers: { 'X-N8N-API-KEY': apiKey, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(await r.text());
  const result = await r.json();
  const wfId = result.id;

  // 激活
  await fetch(`${n8nUrl.replace(/\/+$/, '')}/api/v1/workflows/${wfId}/activate`, {
    method: 'POST', headers: { 'X-N8N-API-KEY': apiKey },
  }).catch(() => {});

  return { id: wfId, workflow: result, webhookUrl: webhookPath ? `${n8nUrl.replace(/\/+$/, '')}/webhook/${webhookPath}` : null };
}

export async function frontendExecute(wfId, n8nUrl, apiKey) {
  // 需要先查询 webhook 节点 path
  const r = await fetch(`${n8nUrl.replace(/\/+$/, '')}/api/v1/workflows/${wfId}`, {
    headers: { 'X-N8N-API-KEY': apiKey },
  });
  const wf = await r.json();
  let webhookPath = '';
  for (const n of wf.nodes || []) {
    if (n.type?.endsWith('webhook')) {
      webhookPath = n.webhookId || n.parameters?.path || '';
      break;
    }
  }
  if (!webhookPath) throw new Error('该工作流没有 Webhook 触发器，无法远程执行');
  const resp = await fetch(`${n8nUrl.replace(/\/+$/, '')}/webhook/${webhookPath}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ping: true }),
  });
  return resp.ok ? '工作流已触发执行，ping 已发送' : `执行失败: ${await resp.text()}`;
}

/* ── 辅助函数（同 server.py _add_webhook_trigger） ── */
function addWebhookTrigger(nodes, connections) {
  for (const n of nodes) {
    if (n.type?.endsWith('webhook')) {
      n.parameters = n.parameters || {};
      n.parameters.httpMethod = n.parameters.httpMethod || 'POST';
      return n.parameters.path || 'ping-' + Math.random().toString(36).slice(2, 8);
    }
  }
  for (const n of nodes) {
    if (n.type?.endsWith('manualTrigger')) {
      const path = 'ping-' + Math.random().toString(36).slice(2, 8);
      n.type = 'n8n-nodes-base.webhook';
      n.typeVersion = 1;
      n.parameters = { httpMethod: 'POST', path, options: {} };
      return path;
    }
  }
  const path = 'ping-' + Math.random().toString(36).slice(2, 8);
  for (const n of nodes) {
    const pos = n.position || [0, 0];
    if (pos[0] < 300) n.position = [pos[0] + 300, pos[1]];
  }
  nodes.unshift({ name: 'Webhook (Trigger)', type: 'n8n-nodes-base.webhook', typeVersion: 1, position: [0, 250], parameters: { httpMethod: 'POST', path, options: {} } });
  return path;
}

function convertConnections(nodes, connections) {
  const newConn = {};
  for (const [srcKey, outputs] of Object.entries(connections)) {
    const srcName = srcKey.match(/^\d+$/) ? (nodes[parseInt(srcKey)]?.name || srcKey) : srcKey;
    const newOutputs = {};
    for (const [outKey, targets] of Object.entries(outputs)) {
      const list = Array.isArray(targets) ? targets : [];
      const newTargets = [];
      for (const t of list) {
        if (typeof t === 'number') {
          const tname = nodes[t]?.name || String(t);
          newTargets.push({ node: tname, type: '1', index: 0 });
        } else if (typeof t === 'object' && t !== null) {
          newTargets.push(t.node ? t : { node: String(t), type: '1', index: 0 });
        }
      }
      if (newTargets.length) newOutputs.main = [newTargets];
    }
    if (Object.keys(newOutputs).length) newConn[srcName] = newOutputs;
  }
  return newConn;
}
