// ── Toast 通知 ──────────────────────────────────────

let toastTimer = null;

export function showToast(message, type = 'info', duration = 4000) {
  const colors = {
    info: { bg: '#1e40af', text: '#fff' },
    success: { bg: '#166534', text: '#fff' },
    warning: { bg: '#92400e', text: '#fff' },
    error: { bg: '#991b1b', text: '#fff' },
  };
  const c = colors[type] || colors.info;

  // 移除旧 toast
  const old = document.getElementById('app-toast');
  if (old) old.remove();
  if (toastTimer) clearTimeout(toastTimer);

  const el = document.createElement('div');
  el.id = 'app-toast';
  el.textContent = message;
  el.style.cssText = `
    position:fixed;bottom:80px;left:50%;transform:translateX(-50%);
    background:${c.bg};color:${c.text};
    padding:12px 24px;border-radius:10px;font-size:15px;
    z-index:9999;box-shadow:0 4px 20px rgba(0,0,0,.3);
    animation:toastIn .3s ease;
    max-width:90%;text-align:center;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  `;
  document.body.appendChild(el);

  toastTimer = setTimeout(() => {
    el.style.animation = 'toastOut .3s ease';
    setTimeout(() => el.remove(), 300);
  }, duration);
}

// 注入 CSS 动画
const style = document.createElement('style');
style.textContent = `
  @keyframes toastIn{from{opacity:0;transform:translateX(-50%) translateY(20px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}
  @keyframes toastOut{from{opacity:1;transform:translateX(-50%) translateY(0)}to{opacity:0;transform:translateX(-50%) translateY(20px)}}
`;
document.head.appendChild(style);
