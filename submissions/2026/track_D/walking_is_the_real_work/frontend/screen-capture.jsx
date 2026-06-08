// Capture screen — 3-step flow: 取景 → 提色 → 题字 → 完成
// Hackathon build: Step 2 / Step 3 now talk to the FastAPI backend that
// runs Gemma 4 4B Multimodal. KIND_PALETTE is kept only as the offline
// preview / failure-fallback set.

const API_BASE = window.GEMMA_API_BASE || "";

const KIND_OPTIONS = [
  { id: 'brick',     label: '砖 墙' },
  { id: 'leaf',      label: '落 叶' },
  { id: 'facade',    label: '楼 墙' },
  { id: 'fog',       label: '雾 水' },
  { id: 'wisteria',  label: '花 影' },
  { id: 'awning',    label: '招 牌' },
];

// Local previews used while the user is still framing — the real palette
// arrives from Gemma 4 once the shutter fires.
const KIND_PREVIEW = {
  brick:    [['#A14328', '砖 红'], ['#8A8378', '尘 灰'], ['#D7C2A0', '土 黄'], ['#3B2C20', '深 褐']],
  leaf:     [['#C9A24E', '初 黄'], ['#6B5A2E', '苔 褐'], ['#E8DFC4', '麻 白'], ['#2F3A1F', '墨 绿']],
  facade:   [['#E6C58A', '奶 油'], ['#C97B4B', '日 暮'], ['#6E3B26', '赭 石'], ['#2A2118', '夜 至']],
  fog:      [['#8B97A0', '雾 青'], ['#C4CBCE', '霜 灰'], ['#4D585F', '远 山'], ['#DCDBD3', '茧 白']],
  wisteria: [['#6F5A8C', '紫 藤'], ['#C7B8D6', '霭 紫'], ['#3E3450', '夜 紫'], ['#E5D6E5', '残 樱']],
  awning:   [['#2F4A6E', '雨 蓝'], ['#B9C7D6', '海 雾'], ['#1A2434', '深 蓝'], ['#D5BFA2', '麻 绳']],
};

const DIM_OPTIONS = [
  { id: '01', zh: '01 嗅觉' },
  { id: '02', zh: '02 视觉' },
  { id: '03', zh: '03 听觉' },
  { id: '04', zh: '04 触觉' },
];

const PICKER_POS = [
  { x: 30, y: 32 },
  { x: 72, y: 28 },
  { x: 60, y: 68 },
  { x: 22, y: 76 },
];

// Convert the SVG plate the user is looking at into a JPEG blob, so we
// can post a real image to the backend even when the browser camera is
// not available (i.e. desktop preview).
async function plateToBlob(svgEl) {
  const svgString = new XMLSerializer().serializeToString(svgEl);
  const url = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(svgString)));
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const c = document.createElement("canvas");
      c.width = 320; c.height = 320;
      c.getContext("2d").drawImage(img, 0, 0, 320, 320);
      c.toBlob(b => b ? resolve(b) : reject(new Error("toBlob failed")), "image/jpeg", 0.9);
    };
    img.onerror = reject;
    img.src = url;
  });
}

async function postPalette(blob) {
  const fd = new FormData();
  fd.append("image", blob, "frame.jpg");
  const r = await fetch(`${API_BASE}/api/extract_palette`, { method: "POST", body: fd });
  if (!r.ok) throw new Error(`extract_palette ${r.status}`);
  const j = await r.json();
  return j.palette.map(p => ({ hex: p.hex, zh: p.zh }));
}

async function postInscribe(palette, place, geo) {
  const r = await fetch(`${API_BASE}/api/inscribe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ palette, place, geo }),
  });
  if (!r.ok) throw new Error(`inscribe ${r.status}`);
  return r.json();
}

function CaptureScreen({ navigate, accent, onSave }) {
  const [step, setStep] = React.useState(1);
  const [kind, setKind] = React.useState('brick');
  const [palette, setPalette] = React.useState(() =>
    KIND_PREVIEW.brick.map(([hex, zh]) => ({ hex, zh }))
  );
  const [meta, setMeta] = React.useState({
    title: '',
    place: '巨鹿路 821 号',
    geo: '31.2168° N   121.4571° E',
    dimension: '02 视觉维度',
    poem: '',
  });
  const [extractStatus, setExtractStatus] = React.useState('idle');
  const [inscribeStatus, setInscribeStatus] = React.useState('idle');
  const [inArchive, setInArchive] = React.useState(false);
  const plateRef = React.useRef(null);

  const pickKind = (k) => {
    setKind(k);
    setPalette(KIND_PREVIEW[k].map(([hex, zh]) => ({ hex, zh })));
  };

  // Real shutter: capture the current plate as JPEG and ask Gemma 4 to
  // pick the palette. Falls back to the preview palette on network error.
  const shoot = async () => {
    setStep(2);
    setExtractStatus('loading');
    try {
      const svg = plateRef.current?.querySelector('svg');
      if (!svg) throw new Error('no plate svg');
      const blob = await plateToBlob(svg);
      const next = await postPalette(blob);
      setPalette(next);
      setExtractStatus('done');
    } catch (e) {
      console.warn('palette extract failed, using preview', e);
      setExtractStatus('error');
    }
  };

  const inscribeAndSave = async () => {
    setInscribeStatus('loading');
    try {
      const r = await postInscribe(palette, meta.place, meta.geo);
      setMeta(m => ({
        ...m,
        title: m.title || r.title || '无题',
        poem:  m.poem  || r.line  || '',
      }));
      setInArchive(!!r.in_archive);
      setInscribeStatus('done');
    } catch (e) {
      console.warn('inscribe failed', e);
      setInscribeStatus('error');
    } finally {
      onSave?.({ kind, palette, meta });
      setStep(4);
    }
  };

  const next = () => setStep(s => Math.min(4, s + 1));
  const prev = () => {
    if (step === 1) navigate({ name: 'feed' }, 'back');
    else setStep(s => s - 1);
  };

  const dim = DIM_OPTIONS.find(d => meta.dimension.startsWith(d.id));

  const stepDef = [
    { num: '01', en: 'Frame',    zh: '取 景' },
    { num: '02', en: 'Extract',  zh: '提 色' },
    { num: '03', en: 'Inscribe', zh: '题 字' },
    { num: '04', en: 'Done',     zh: '入 册' },
  ];

  return (
    <div className="screen capture" data-screen-label={`Capture · step ${step}`}>
      <div className="topbar">
        <button className="back" onClick={prev} aria-label="返回">
          <svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg>
        </button>
        <div className="title">
          采 · 集
          <em>NEW SPECIMEN</em>
        </div>
        <button className="icn" onClick={() => navigate({ name: 'feed' }, 'back')} aria-label="关闭">
          <svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>
        </button>
      </div>

      <div className="scroll">
        <div className="steps">
          {stepDef.map((s, i) => (
            <div key={i}
                 className={`step ${step === i+1 ? 'active' : ''} ${step > i+1 ? 'done' : ''}`}>
              <span className="num">{s.num}</span>
              <span>{s.zh}</span>
            </div>
          ))}
        </div>

        {step === 1 && (
          <Step1Frame kind={kind} setKind={pickKind} palette={palette}
                      plateRef={plateRef} onShoot={shoot}/>
        )}
        {step === 2 && (
          <Step2Extract kind={kind} palette={palette} setPalette={setPalette}
                        status={extractStatus}
                        onBack={prev} onNext={next}/>
        )}
        {step === 3 && (
          <Step3Inscribe meta={meta} setMeta={setMeta} dim={dim}
                         status={inscribeStatus}
                         onBack={prev} onNext={inscribeAndSave}/>
        )}
        {step === 4 && (
          <Step4Done meta={meta} accent={accent} inArchive={inArchive}
                     onView={() => navigate({ name: 'feed' })}/>
        )}
      </div>
    </div>
  );
}

// ── Step 1 ─────────────────────────────────────────────────────
function Step1Frame({ kind, setKind, palette, plateRef, onShoot }) {
  return (
    <div className="cap-stage">
      <h2>把这片颜色框进来</h2>
      <p className="lead">Frame · 对着想保留的色彩,按下快门 → Gemma 4 取色</p>

      <div className="viewfinder" ref={plateRef}>
        <PlateSVG kind={kind} palette={palette}/>
        <div className="crosshair">
          <div className="corner tl"/><div className="corner tr"/>
          <div className="corner bl"/><div className="corner br"/>
        </div>
        <span className="vlabel">F 2.8 &nbsp;·&nbsp; 1/250 &nbsp;·&nbsp; ISO 200</span>
        <div className="reticle"/>
      </div>

      <div className="viewfinder-pick">
        {KIND_OPTIONS.map(k => (
          <button key={k.id}
                  className={k.id === kind ? 'active' : ''}
                  onClick={() => setKind(k.id)}>
            {k.label}
          </button>
        ))}
      </div>

      <button className="snap" onClick={onShoot} aria-label="拍下"/>
    </div>
  );
}

// ── Step 2 ─────────────────────────────────────────────────────
function Step2Extract({ kind, palette, setPalette, status, onBack, onNext }) {
  const pcts = React.useMemo(() => {
    const seed = palette.map(p => p.hex).join('').length;
    return [40, 26, 20, 14].map((b, i) => b + ((seed + i*3) % 4) - 2);
  }, [palette]);

  const banner = {
    loading: 'Gemma 4 4B 多模态识图中…',
    done:    '四种颜色被提了出来',
    error:   '本机离线 · 已退回到预设色',
    idle:    '四种颜色被提了出来',
  }[status];

  return (
    <div className="cap-stage">
      <h2>{banner}</h2>
      <p className="lead">Extract · 自动取色完成 · 可改写名称</p>

      <div className="extract-photo">
        <PlateSVG kind={kind} palette={palette}/>
        {PICKER_POS.map((pos, i) => (
          <div key={i} className="picker"
               style={{
                 left: `${pos.x}%`,
                 top: `${pos.y}%`,
                 background: palette[i]?.hex,
               }}>
            <span className="leg"/>
          </div>
        ))}
      </div>

      <div className="extract-list">
        {palette.map((p, i) => (
          <div key={i} className="extract-row">
            <div className="chip" style={{ background: p.hex }}/>
            <div className="info">
              <input className="name" value={p.zh}
                     onChange={(e) => {
                       const next = palette.slice();
                       next[i] = { ...next[i], zh: e.target.value };
                       setPalette(next);
                     }}/>
              <span className="hex">{p.hex.toUpperCase()}</span>
            </div>
            <span className="pct">{pcts[i]}%</span>
          </div>
        ))}
      </div>

      <div className="cap-actions">
        <button onClick={onBack}>重 新 取 景</button>
        <button className="primary" onClick={onNext}
                disabled={status === 'loading'}>继 续 题 字</button>
      </div>
    </div>
  );
}

// ── Step 3 ─────────────────────────────────────────────────────
function Step3Inscribe({ meta, setMeta, dim, status, onBack, onNext }) {
  const upd = (k) => (e) => setMeta(m => ({ ...m, [k]: e.target.value }));

  return (
    <div className="cap-stage">
      <h2>给它写两句话</h2>
      <p className="lead">
        Inscribe · 留空 → Gemma 4 调用工具查街区档案 + 自动题字
      </p>

      <div className="compose-field">
        <label><span className="zh">题 名</span> Title</label>
        <input value={meta.title} placeholder="留空将由模型自动生成"
               onChange={upd('title')}/>
      </div>

      <div className="compose-field">
        <label><span className="zh">位 置</span> Where</label>
        <input value={meta.place} onChange={upd('place')}/>
      </div>

      <div className="compose-field">
        <label><span className="zh">维 度</span> Dimension</label>
        <div className="dim-grid">
          {DIM_OPTIONS.map(d => (
            <button key={d.id}
                    className={meta.dimension.startsWith(d.id) ? 'active' : ''}
                    onClick={() => setMeta(m => ({ ...m, dimension: `${d.id} ${d.zh.split(' ')[1]}维度` }))}>
              {d.zh}
            </button>
          ))}
        </div>
      </div>

      <div className="compose-field">
        <label><span className="zh">一 句</span> A Line</label>
        <textarea rows={2} placeholder="留空将由模型自动生成"
                  value={meta.poem}
                  onChange={upd('poem')}/>
      </div>

      <div className="cap-actions">
        <button onClick={onBack}>上 一 步</button>
        <button className="primary" onClick={onNext}
                disabled={status === 'loading'}>
          {status === 'loading' ? 'Gemma 调用工具中…' : '收 入 图 鉴'}
        </button>
      </div>
    </div>
  );
}

// ── Step 4 ─────────────────────────────────────────────────────
function Step4Done({ meta, accent, inArchive, onView }) {
  return (
    <div className="cap-done">
      <div className="seal" style={{ borderColor: accent, color: accent }}>收</div>
      <h2>已收入图鉴</h2>
      <p className="lead">No. 0243 &nbsp;·&nbsp; {meta.title || '无题'}</p>
      {inArchive && (
        <p className="lead" style={{ color: accent, marginTop: 6 }}>
          ✓ 该街区已在历史风貌保护名录,本次采集计入存档
        </p>
      )}
      <div className="nice">「 这一片颜色,归你了 」</div>
      <div className="cap-actions" style={{ marginTop: 40 }}>
        <button className="primary" onClick={onView}>回 到 图 鉴 册</button>
      </div>
    </div>
  );
}

Object.assign(window, { CaptureScreen });
