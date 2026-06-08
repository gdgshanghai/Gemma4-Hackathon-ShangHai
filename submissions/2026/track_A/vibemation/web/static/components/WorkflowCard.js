// ── 工作流卡片 ──────────────────────────────────────
import { html, useState } from '../preact.js';
import { apiDeploy, apiExecute } from '../api.js';
import { frontendDeploy, frontendExecute } from '../frontend-agent.js';

function downloadJSON(wf) {
  const blob = new Blob([JSON.stringify(wf, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = (wf.name || 'workflow') + '.json';
  a.click(); URL.revokeObjectURL(url);
}

function copyText(text) {
  navigator.clipboard.writeText(text).then(() => {
    const el = document.createElement('div');
    el.textContent = '✅ 已复制';
    el.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#22c55e;color:#fff;padding:8px 16px;border-radius:8px;font-size:13px;z-index:9999;animation:fadeOut 1.5s forwards';
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 1500);
  });
}

export default function WorkflowCard({ workflow, instance, frontendMode }) {
  const [expanded, setExpanded] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState(null);
  const [wfId, setWfId] = useState(null);
  const [webhookUrl, setWebhookUrl] = useState(null);

  const handleDeploy = async () => {
    if (!instance) { alert('请先选择 n8n 实例'); return; }
    setDeploying(true); setResult(null);
    try {
      if (frontendMode && !instance.builtin && instance.key) {
        // 前端模式：用户实例，前端直连 n8n
        const res = await frontendDeploy(workflow, instance.url, instance.key);
        setWfId(res.id);
        setWebhookUrl(res.webhookUrl);
        setResult(`✅ 部署成功 (ID: ${res.id})`);
      } else {
        // 后端模式：默认实例走后端
        const { ok, data } = await apiDeploy(workflow, instance.url, instance.key || '');
        if (ok) {
          setWfId(data.workflow?.id);
          setWebhookUrl(data.workflow?.webhook_url);
          setResult(`✅ 部署成功 (ID: ${data.workflow?.id})`);
        } else {
          setResult('❌ ' + (data.detail || '失败'));
        }
      }
    } catch (e) {
      setResult('❌ ' + e.message);
    }
    setDeploying(false);
  };

  const handleExecute = async () => {
    if (!wfId || !instance) return;
    setExecuting(true); setResult('⏳ 执行中...');
    try {
      if (frontendMode && !instance.builtin && instance.key) {
        const msg = await frontendExecute(wfId, instance.url, instance.key);
        setResult('✅ ' + msg);
      } else if (webhookUrl) {
        // 后端模式：走后端 execute 接口
        const { ok, data } = await apiExecute(wfId, instance.url, instance.key || '');
        setResult(ok ? '✅ 执行成功! ping 已发送' : '❌ ' + (data.detail || '失败'));
      } else {
        setResult('❌ 没有可触发的 webhook 路径');
      }
    } catch (e) {
      setResult('❌ ' + e.message);
    }
    setExecuting(false);
  };

  return html`
    <div class="msg workflow">
      <div class="wf-header" onClick=${() => setExpanded(!expanded)}>
        <span class="wf-title">${workflow.name || '未命名'}</span>
        <span class="wf-meta">${workflow.nodes?.length || 0} 节点</span>
        <span style="color:#007aff;font-size:10px">${expanded ? '收起' : '展开'}</span>
      </div>
      ${expanded ? html`<div class="code-block">${JSON.stringify(workflow, null, 2)}</div>` : ''}
      <div class="wf-actions">
        <button style="background:#6366f1" onClick=${() => copyText(JSON.stringify(workflow, null, 2))}>📋 复制</button>
        <button style="background:#8b5cf6" onClick=${() => downloadJSON(workflow)}>⬇ 下载</button>
        <button style="background:#28a745" onClick=${handleDeploy} disabled=${deploying}>
          ${deploying ? '部署中...' : '🚀 部署到 n8n'}
        </button>
        ${wfId ? html`
          <button style="background:#f59e0b" onClick=${handleExecute} disabled=${executing}>
            ${executing ? '执行中...' : '▶️ 执行工作流'}
          </button>
        ` : ''}
        ${result ? html`<span style="font-size:11px;color:#666;align-self:center">${result}</span>` : ''}
      </div>
    </div>
  `;
}
