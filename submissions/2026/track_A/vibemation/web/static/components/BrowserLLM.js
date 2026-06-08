/**
 * BrowserLLM — 浏览器端 LLM 组件
 *
 * 四态渲染: idle / loading / ready / error
 *
 * Props:
 *   provider     — 当前选中的 provider 对象
 *   browserLLM   — { status, progress, statusText, engine }
 *   setBrowserLLM — setter
 *   onSend       — (messages) => Promise<string> 推理回调
 *   onSwitchOnline — () => void 切换回在线 API
 */
import { html, useState, useEffect, useRef } from '../preact.js';
import { checkWebGPU } from '../llm/webllm.js';
import { getProviderById } from '../store.js';

/* ── 模型大小映射 ──────────────────────────── */
const MODEL_SIZES = {
  webllm_e2b:   { label: 'Gemma 4 E2B Q4',  download: '~2.5 GB', memory: '~3 GB',  estTime: '30-60s', source: 'huggingface.co/mlc-ai' },
  webllm_e4b:   { label: 'Gemma 4 E4B Q4',  download: '~4.5 GB', memory: '~5 GB',  estTime: '60-120s', source: 'huggingface.co/mlc-ai' },
  webllm_e4b_h: { label: 'Gemma 4 E4B Q5',  download: '~5.5 GB', memory: '~6 GB',  estTime: '90-180s', source: 'huggingface.co/mlc-ai' },
  litertlm_e2b:  { label: 'Gemma 4 E2B Q4',  download: '~2.5 GB', memory: '~3 GB',  estTime: '30-60s', source: 'gstatic.com (Edge Gallery)' },
  litertlm_e4b:  { label: 'Gemma 4 E4B Q4',  download: '~4.5 GB', memory: '~5 GB',  estTime: '60-120s', source: 'gstatic.com (Edge Gallery)' },
  litertlm_e4b_h:{ label: 'Gemma 4 E4B Q5',  download: '~5.5 GB', memory: '~6 GB',  estTime: '90-180s', source: 'gstatic.com (Edge Gallery)' },
};

/* =====================================================
   确认弹窗
   ===================================================== */
function ConfirmDialog({ providerId, onConfirm, onCancel }) {
  const size = MODEL_SIZES[providerId] || {};
  const [webgpuOk, setWebgpuOk] = useState(null);
  const [storageInfo, setStorageInfo] = useState(null);

  useEffect(() => {
    checkWebGPU().then(setWebgpuOk);
    if (navigator.storage?.estimate) {
      navigator.storage.estimate().then(est => {
        const freeGB = (est.quota - est.usage) / (1024**3);
        setStorageInfo({ free: freeGB.toFixed(1), need: size.memory || '?' });
      });
    }
  }, []);

  return html`
    <div style="position:fixed;inset:0;background:rgba(0,0,0,.65);z-index:2000;
                display:flex;align-items:center;justify-content:center"
         onClick=${(e) => { if (e.target === e.currentTarget) onCancel(); }}>
      <div style="background:#1a1f2e;color:#e4e7eb;border-radius:16px;padding:28px 32px;
                  width:90%;max-width:460px;box-shadow:0 20px 60px rgba(0,0,0,.5)">
        <div style="font-size:22px;font-weight:700;margin-bottom:16px">⚠️ 下载端侧模型</div>

        <div style="background:rgba(255,255,255,.04);border-radius:10px;padding:16px;margin-bottom:16px;font-size:14px;line-height:1.7">
          <div style="display:flex;justify-content:space-between;padding:4px 0">
            <span style="color:#9ca3af">模型</span>
            <span>${size.label || providerId}</span>
          </div>
          <div style="display:flex;justify-content:space-between;padding:4px 0">
            <span style="color:#9ca3af">下载大小</span>
            <span>${size.download || '?'}</span>
          </div>
          <div style="display:flex;justify-content:space-between;padding:4px 0">
            <span style="color:#9ca3af">加载后内存</span>
            <span>${size.memory || '?'}</span>
          </div>
          <div style="display:flex;justify-content:space-between;padding:4px 0">
            <span style="color:#9ca3af">预计耗时</span>
            <span>${size.estTime || '?'}</span>
          </div>
          <div style="display:flex;justify-content:space-between;padding:4px 0">
            <span style="color:#9ca3af">WebGPU</span>
            <span style="color:${webgpuOk === true ? '#22c55e' : webgpuOk === false ? '#ef4444' : '#9ca3af'}">
              ${webgpuOk === null ? '检查中...' : webgpuOk ? '✅ 支持' : '❌ 不支持'}
            </span>
          </div>
          ${storageInfo ? html`
            <div style="display:flex;justify-content:space-between;padding:4px 0">
              <span style="color:#9ca3af">可用存储</span>
              <span style="color:${parseFloat(storageInfo.free) > parseFloat(storageInfo.need) ? '#22c55e' : '#ef4444'}">
                ${storageInfo.free} GB ${parseFloat(storageInfo.free) < parseFloat(storageInfo.need) ? '(不足)' : ''}
              </span>
            </div>
          ` : ''}
        </div>

        ${webgpuOk === false ? html`
          <div style="background:rgba(239,68,68,.15);color:#ef4444;padding:10px 14px;border-radius:8px;font-size:13px;margin-bottom:14px">
            ❌ 当前浏览器不支持 WebGPU，无法运行端侧模型。请使用 Chrome 113+ 或切换到在线 API。
          </div>
        ` : ''}
        ${storageInfo && parseFloat(storageInfo.free) < parseFloat(storageInfo.need) ? html`
          <div style="background:rgba(245,158,11,.15);color:#f59e0b;padding:10px 14px;border-radius:8px;font-size:13px;margin-bottom:14px">
            ⚠️ 可用存储空间不足（剩余 ${storageInfo.free} GB，需要 ${storageInfo.need}），请清理缓存后重试。
          </div>
        ` : ''}

        <div style="display:flex;gap:10px;justify-content:flex-end">
          <button onClick=${onCancel}
            style="padding:10px 20px;border:1px solid #374151;border-radius:8px;background:transparent;color:#9ca3af;cursor:pointer;font-size:14px">
            取消
          </button>
          <button onClick=${onConfirm}
            disabled=${webgpuOk === false}
            style="padding:10px 20px;border:none;border-radius:8px;background:${webgpuOk === false ? '#374151' : '#3b82f6'};color:#fff;cursor:${webgpuOk === false ? 'not-allowed' : 'pointer'};font-size:14px">
            确认下载
          </button>
        </div>
      </div>
    </div>
  `;
}

/* =====================================================
   进度条
   ===================================================== */
function ProgressBar({ progress, statusText }) {
  return html`
    <div style="width:100%">
      <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px">
        <span style="color:#9ca3af">${statusText || '下载中...'}</span>
        <span style="color:#e4e7eb;font-weight:600">${Math.round(progress * 100)}%</span>
      </div>
      <div style="width:100%;height:8px;background:#374151;border-radius:4px;overflow:hidden">
        <div style="width:${progress * 100}%;height:100%;background:linear-gradient(90deg,#3b82f6,#8b5cf6);border-radius:4px;transition:width .3s ease"></div>
      </div>
    </div>
  `;
}

/* =====================================================
   BrowserLLM 主组件
   ===================================================== */
export default function BrowserLLM({ provider, browserLLM, setBrowserLLM, onSend, onSwitchOnline }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const chatRef = useRef(null);

  const prov = getProviderById(provider);

  // 自动滚动到底部
  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [messages]);

  // ── 空闲态: 显示加载按钮 ──────────────────────
  if (browserLLM.status === 'idle') {
    return html`
      <div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;padding:40px;color:#9ca3af">
        <div style="font-size:48px">🧠</div>
        <div style="font-size:18px;font-weight:600;color:#e4e7eb">${prov?.label || '未知模型'}</div>
        <div style="font-size:14px;text-align:center;max-width:360px;line-height:1.6">
          ${prov?.type === 'webllm' ? html`
            ⏳ Gemma 4 端侧模型正在适配 WebLLM，暂不可用。<br/>
            预计模型将从 Hugging Face 下载 (~2.5-5.5 GB)，<br/>
            请先使用「在线 API」模式。
          ` : html`
            Gemma 4 可通过 Google Edge Gallery 下载到本地运行！<br/>
            模型从 gstatic.com 下载 (~2.5-5.5 GB)，<br/>
            LiteRT SDK 集成中，敬请期待。
          `}
        </div>
        <div style="font-size:12px;color:#6b7280;margin-top:4px">
          ${prov?.type === 'webllm' ? '下载源: huggingface.co/mlc-ai' : '下载源: Google LiteRT SDK'}
        </div>
      </div>
    `;
  }

  // ── 加载态: 进度条 ──────────────────────────
  if (browserLLM.status === 'loading') {
    return html`
      <div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;padding:40px">
        <div style="font-size:36px">⏳</div>
        <div style="font-size:16px;color:#e4e7eb;font-weight:600">正在下载模型...</div>
        <div style="width:80%;max-width:400px">
          <${ProgressBar} progress=${browserLLM.progress} statusText=${browserLLM.statusText} />
        </div>
        <div style="font-size:12px;color:#6b7280;margin-top:8px">
          下载完成后自动加载，断点续传自动支持
        </div>
      </div>
    `;
  }

  // ── 错误态 ────────────────────────────────
  if (browserLLM.status === 'error') {
    return html`
      <div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;padding:40px">
        <div style="font-size:48px">❌</div>
        <div style="font-size:18px;font-weight:600;color:#ef4444">模型加载失败</div>
        <div style="font-size:14px;color:#9ca3af;text-align:center;max-width:400px;line-height:1.6">
          ${browserLLM.error || '未知错误，请重试或切换到在线 API'}
        </div>
        <div style="display:flex;gap:10px">
          <button onClick=${doLoad}
            style="padding:10px 24px;border:none;border-radius:10px;background:#3b82f6;color:#fff;font-size:14px;cursor:pointer">
            🔄 重试
          </button>
          <button onClick=${onSwitchOnline}
            style="padding:10px 24px;border:1px solid #374151;border-radius:10px;background:transparent;color:#9ca3af;font-size:14px;cursor:pointer">
            ☁️ 切换到在线 API
          </button>
        </div>
      </div>
    `;
  }

  // ── 就绪态: 聊天界面 ────────────────────────
  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput('');
    setMessages(m => [...m, { role: 'user', content: text }]);
    setSending(true);
    try {
      const allMsgs = [...messages, { role: 'user', content: text }];
      const reply = await onSend(allMsgs);
      setMessages(m => [...m, { role: 'assistant', content: reply }]);
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', content: '❌ 推理失败: ' + e.message }]);
    }
    setSending(false);
  };

  return html`
    <div style="flex:1;display:flex;flex-direction:column;min-height:0">
      <!-- 模型就绪提示条 -->
      <div style="display:flex;align-items:center;gap:8px;padding:8px 16px;background:rgba(34,197,94,.1);border-bottom:1px solid rgba(34,197,94,.2);font-size:13px">
        <span style="color:#22c55e">🟢</span>
        <span style="color:#e4e7eb">${prov?.label || '端侧模型'} 已就绪</span>
        <span style="color:#22c55e;font-size:12px">（浏览器本地推理）</span>
        <button onClick=${doUnload}
          style="margin-left:auto;padding:4px 12px;border:1px solid #374151;border-radius:6px;background:transparent;color:#9ca3af;cursor:pointer;font-size:12px">
          卸载模型
        </button>
      </div>

      <!-- 消息列表 -->
      <div ref=${chatRef} style="flex:1;overflow-y:auto;padding:16px 20px;display:flex;flex-direction:column;gap:10px">
        ${messages.length === 0 ? html`
          <div style="flex:1;display:flex;align-items:center;justify-content:center;color:#6b7280;font-size:14px">
            模型已就绪，开始对话
          </div>
        ` : messages.map((msg, i) => html`
          <div key=${i} class="msg ${msg.role}"
            style="max-width:80%;padding:10px 16px;border-radius:12px;font-size:15px;line-height:1.6;white-space:pre-wrap;word-break:break-word;
              ${msg.role === 'user'
                ? 'background:#3b82f6;color:#fff;align-self:flex-end;border-bottom-right-radius:4px'
                : 'background:rgba(255,255,255,.06);color:#e4e7eb;align-self:flex-start;border-bottom-left-radius:4px'}">
            ${msg.content}
          </div>
        `)}
        ${sending ? html`<div style="color:#6b7280;font-size:13px;align-self:flex-start">思考中...</div>` : ''}
      </div>

      <!-- 输入栏 -->
      <div style="display:flex;gap:8px;padding:12px 16px;background:#1a1f2e;border-top:1px solid #2d3748">
        <input type="text" placeholder="输入消息..." value=${input}
          onInput=${(e) => setInput(e.target.value)}
          onKeyDown=${(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
          style="flex:1;padding:10px 16px;border:1px solid #374151;border-radius:20px;background:#0f1419;color:#e4e7eb;font-size:15px;outline:none"
          disabled=${sending} />
        <button onClick=${handleSend} disabled=${sending || !input.trim()}
          style="padding:10px 20px;border:none;border-radius:20px;background:${sending || !input.trim() ? '#374151' : '#3b82f6'};color:#fff;font-size:14px;cursor:${sending || !input.trim() ? 'not-allowed' : 'pointer'}">
          ${sending ? '...' : '发送'}
        </button>
      </div>
    </div>
  `;

  // ── 内部函数 ──────────────────────────────
  async function doLoad() {
    setBrowserLLM(s => ({ ...s, status: 'loading', progress: 0, statusText: '正在下载...' }));
    try {
      const isWebllm = prov?.type === 'webllm';
      let mod;
      if (isWebllm) {
        mod = await import('../llm/webllm.js');
      } else {
        mod = await import('../llm/litertlm.js');
      }

      // 检查 WebGPU
      const gpuOk = await mod.checkWebGPU();
      if (!gpuOk) {
        setBrowserLLM(s => ({ ...s, status: 'error', error: '当前浏览器不支持 WebGPU，请使用 Chrome 113+ 或切换到在线 API', progress: 0 }));
        return;
      }

      const engine = await mod.loadModel(prov.model, (p) => {
        setBrowserLLM(s => ({
          ...s,
          progress: p.progress || 0,
          statusText: p.text || '下载中...',
        }));
      });
      // 保存 generate 函数引用
      setBrowserLLM(s => ({ ...s, status: 'ready', engine, progress: 1, statusText: '已就绪', generateFn: mod.generate, unloadFn: mod.unload }));
    } catch (e) {
      setBrowserLLM(s => ({ ...s, status: 'error', error: e.message || String(e), progress: 0 }));
    }
  }

  async function doUnload() {
    if (browserLLM.unloadFn) browserLLM.unloadFn();
    setMessages([]);
    setBrowserLLM({ status: 'idle', progress: 0, engine: null, statusText: '', generateFn: null, unloadFn: null, error: null });
  }
}
