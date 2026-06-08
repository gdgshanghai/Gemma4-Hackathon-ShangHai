// ── n8n 实例管理（Modal 添加）────────────────────────
import { html, useState } from '../preact.js';
import { upsertInstance, removeInstance } from '../store.js';

export default function InstanceManager({ instances, setInstances, currentInstance, setCurrentInstance }) {
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState(null);
  const [fName, setFName] = useState('');
  const [fUrl, setFUrl] = useState('https://');
  const [fKey, setFKey] = useState('');
  const [menuIdx, setMenuIdx] = useState(null);
  const isEdit = !!editId;

  const openAdd = () => { setEditId(null); setFName(''); setFUrl('https://'); setFKey(''); setShowModal(true); };
  const openEdit = (inst) => { setEditId(inst.id); setFName(inst.name); setFUrl(inst.url); setFKey(inst.key || ''); setShowModal(true); };
  const save = () => {
    if (!fName || !fUrl) return;
    setInstances(upsertInstance(instances, { id: editId || Date.now().toString(36), name: fName, url: fUrl.replace(/\/+$/, ''), key: fKey }));
    setShowModal(false);
  };

  return html`
    <div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
        <label>n8n 实例</label>
        <button class="btn btn-primary btn-sm" onClick=${openAdd}>+</button>
      </div>

      <div class="instance-list">
        ${instances.map(inst => html`
          <div class="instance-item ${currentInstance?.id === inst.id ? 'active' : ''}"
               onClick=${() => setCurrentInstance(inst)}
               style="position:relative"
               title=${inst.url}>
            <span class="name">${inst.name}</span>
            <button class="btn btn-sm" style="background:rgba(255,255,255,.1);font-size:14px;line-height:1"
                    onClick=${(e) => { e.stopPropagation(); setMenuIdx(menuIdx === inst.id ? null : inst.id); }}>⋮</button>
            ${menuIdx === inst.id ? html`
              <div style="position:absolute;right:0;top:100%;background:#1a1f2e;border:1px solid #2d3748;border-radius:6px;z-index:10;min-width:140px;box-shadow:0 4px 12px rgba(0,0,0,.4)"
                   onClick=${(e) => e.stopPropagation()}>
                <div style="padding:6px 10px;font-size:11px;color:#6b7280;border-bottom:1px solid #2d3748;word-break:break-all">${inst.url}</div>
                ${!inst.builtin ? html`
                  <div style="padding:8px 12px;cursor:pointer;font-size:12px;color:#ccc;border-bottom:1px solid #2d3748"
                       onClick=${() => { openEdit(inst); setMenuIdx(null); }}>✎ 编辑</div>
                ` : ''}
                <div style="padding:8px 12px;cursor:pointer;font-size:12px;color:#ef4444"
                     onClick=${() => {
                       if (inst.builtin) localStorage.setItem('hide_builtin_' + inst.url, '1');
                       else if (!confirm('删除?')) return;
                       setInstances(instances.filter(i => i.id !== inst.id));
                       setMenuIdx(null);
                     }}>
                  ${inst.builtin ? '🙈 隐藏' : '🗑 删除'}
                </div>
              </div>
            ` : ''}
          </div>
        `)}
      </div>

      ${showModal ? html`
        <div style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:2000;display:flex;align-items:center;justify-content:center"
             onClick=${(e) => { if (e.target === e.currentTarget) setShowModal(false); }}>
          <div style="background:#1a1f2e;border-radius:14px;padding:24px;width:90%;max-width:420px;box-shadow:0 20px 60px rgba(0,0,0,.5);color:#e4e7eb"
               onClick=${(e) => e.stopPropagation()}>
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
              <span style="font-size:18px;font-weight:700">${isEdit ? '✎ 编辑实例' : '➕ 添加 n8n 实例'}</span>
              <span style="cursor:pointer;font-size:20px;color:#6b7280" onClick=${() => setShowModal(false)}>✕</span>
            </div>
            <div style="display:flex;flex-direction:column;gap:12px">
              <input placeholder="实例名称（如 我的服务器）" value=${fName}
                     onInput=${(e) => setFName(e.target.value)}
                     style="padding:10px 12px;border:1px solid #374151;border-radius:8px;background:#0f1419;color:#e4e7eb;font-size:14px;outline:none" />
              <input placeholder="https://n8n.onrender.com" value=${fUrl}
                     onInput=${(e) => setFUrl(e.target.value)}
                     style="padding:10px 12px;border:1px solid #374151;border-radius:8px;background:#0f1419;color:#e4e7eb;font-size:14px;outline:none" />
              <input type="password" placeholder="API Key（用户实例必填）" value=${fKey}
                     onInput=${(e) => setFKey(e.target.value)}
                     style="padding:10px 12px;border:1px solid #374151;border-radius:8px;background:#0f1419;color:#e4e7eb;font-size:14px;outline:none" />
            </div>
            <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:20px">
              <button onClick=${() => setShowModal(false)}
                style="padding:10px 20px;border:1px solid #374151;border-radius:8px;background:transparent;color:#9ca3af;cursor:pointer;font-size:14px">取消</button>
              <button onClick=${save} disabled=${!fName || !fUrl}
                style="padding:10px 20px;border:none;border-radius:8px;background:${!fName || !fUrl ? '#374151' : '#3b82f6'};color:#fff;cursor:${!fName || !fUrl ? 'not-allowed' : 'pointer'};font-size:14px">${isEdit ? '保存' : '添加'}</button>
            </div>
          </div>
        </div>
      ` : ''}
    </div>
  `;
}
