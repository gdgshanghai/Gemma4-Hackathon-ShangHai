// 散步才是正经事 — main app component
// Routes between feed / detail / map / capture inside an iOS frame,
// with a Tweaks panel for paper mode / accent / density / stamp.

const { useState, useMemo, useRef, useEffect } = React;

const DIMENSIONS = [
  { id: 'all',     zh: '全部', en: 'all'     },
  { id: 'visual',  zh: '视觉', en: 'visual'  },
  { id: 'scent',   zh: '气味', en: 'scent'   },
  { id: 'sound',   zh: '声响', en: 'sound'   },
];

// ── App root ────────────────────────────────────────────────────────────
function App() {
  const [t, setTweak] = useTweaks(window.TWEAK_DEFAULTS);
  const [route, setRoute] = useState({ name: 'feed' });
  const [direction, setDirection] = useState('forward');
  const [extraSpecimens, setExtraSpecimens] = useState([]);

  const navigate = (next, dir = 'forward') => {
    setDirection(dir);
    setRoute(next);
  };

  const isNight = t.paper === 'night';
  const allSpecimens = useMemo(
    () => [...extraSpecimens, ...SPECIMENS],
    [extraSpecimens]
  );
  const findSpecimen = (id) => allSpecimens.find(s => s.id === id);

  const saveSpecimen = ({ kind, palette, meta }) => {
    const nextNo = `No. ${(243 + extraSpecimens.length).toString().padStart(4, '0')}`;
    const now = new Date();
    setExtraSpecimens(prev => [{
      id: `local-${Date.now()}`,
      no: nextNo,
      title: meta.title || '无题',
      dimension: meta.dimension || '02 视觉维度',
      place: meta.place,
      geo: meta.geo,
      date: now.toDateString(),
      time: now.toTimeString().slice(0, 5),
      stamp: '新',
      kind,
      palette,
      notes: meta.poem ? [meta.poem] : null,
    }, ...prev]);
  };

  return (
    <div className="stage">
      <IOSDevice width={402} height={874} dark={isNight}>
        <IOSStatusBar dark={isNight}/>

        <div className={`app ${t.paper}`} data-density={t.density}
             style={{ '--accent': t.accent }}>
          <div className="screens">
            <ScreenRouter
              key={`${route.name}-${route.id || ''}`}
              route={route}
              direction={direction}
              tweaks={t}
              specimens={allSpecimens}
              findSpecimen={findSpecimen}
              navigate={navigate}
              saveSpecimen={saveSpecimen}/>
          </div>

          {/* Bottom nav — only on feed + map */}
          {(route.name === 'feed' || route.name === 'map') && (
            <BottomNav active={route.name} navigate={navigate}/>
          )}
        </div>

        <IOSHomeIndicator dark={isNight}/>
      </IOSDevice>

      {/* Tweaks panel */}
      <TweaksPanel title="Tweaks">
        <TweakSection label="纸 色 / Paper"/>
        <TweakRadio
          label="模式"
          value={t.paper}
          options={[
            { value: 'day',   label: '日' },
            { value: 'dusk',  label: '黄昏' },
            { value: 'night', label: '夜' },
          ]}
          onChange={(v) => setTweak('paper', v)}/>

        <TweakSection label="主 题 色 / Accent"/>
        <TweakColor
          label="手写标签 + 按钮 hover"
          value={t.accent}
          options={['#8C2D19', '#2F4A6E', '#3D6A4A', '#6F5A8C', '#C97B4B']}
          onChange={(v) => setTweak('accent', v)}/>

        <TweakSection label="排 版 / Layout"/>
        <TweakRadio
          label="密度"
          value={t.density}
          options={[
            { value: 'compact', label: '紧凑' },
            { value: 'regular', label: '标准' },
            { value: 'relaxed', label: '舒适' },
          ]}
          onChange={(v) => setTweak('density', v)}/>
        <TweakToggle
          label="显示采集印章"
          value={t.stamp}
          onChange={(v) => setTweak('stamp', v)}/>
      </TweaksPanel>
    </div>
  );
}

// ── Router ──────────────────────────────────────────────────────────────
function ScreenRouter({ route, direction, tweaks, specimens, findSpecimen, navigate, saveSpecimen }) {
  const cls = direction === 'back' ? 'backward' : '';
  switch (route.name) {
    case 'feed':
      return <FeedScreen className={cls} tweaks={tweaks}
                         specimens={specimens} navigate={navigate}/>;
    case 'detail':
      return <DetailScreen specimen={findSpecimen(route.id)}
                           navigate={navigate} accent={tweaks.accent}/>;
    case 'map':
      return <MapScreen navigate={navigate} accent={tweaks.accent}/>;
    case 'capture':
      return <CaptureScreen navigate={navigate} accent={tweaks.accent}
                            onSave={saveSpecimen}/>;
    default:
      return null;
  }
}

// ── Bottom nav ──────────────────────────────────────────────────────────
function BottomNav({ active, navigate }) {
  return (
    <div className="bottom-nav">
      <button className={`tab ${active === 'feed' ? 'active' : ''}`}
              onClick={() => navigate({ name: 'feed' }, 'back')}>
        图鉴
        <span className="en">field guide</span>
      </button>
      <button className="capture"
              onClick={() => navigate({ name: 'capture' })}
              aria-label="采集">
        采
      </button>
      <button className={`tab ${active === 'map' ? 'active' : ''}`}
              onClick={() => navigate({ name: 'map' })}>
        地图
        <span className="en">field map</span>
      </button>
    </div>
  );
}

// ── Feed screen ─────────────────────────────────────────────────────────
function FeedScreen({ className, tweaks, specimens, navigate }) {
  const [activeTab, setActiveTab] = useState('all');
  const [exported, setExported] = useState(false);

  const list = useMemo(() => {
    if (activeTab === 'all' || activeTab === 'visual') return specimens;
    return [];
  }, [activeTab, specimens]);

  return (
    <div className={`screen feed ${className}`} data-screen-label="Feed">
      <div className="scroll">
        <div className="masthead">
          <span className="mark">散 步 · 才 是 正 经 事</span>
          <span className="num">Field Notes &nbsp;·&nbsp; v.06</span>
        </div>

        <div className="title-row">
          <h1>色彩标本</h1>
          <div className="sub">
            Chromatic Specimens
            <b>壹 · 五月图鉴册</b>
          </div>
        </div>

        <div className="dayline">
          <span>17 — 22 MAY · MMXXVI</span>
          <span>{specimens.length.toString().padStart(2, '0')} PIECES · SHANGHAI</span>
        </div>

        <nav className="tabs" aria-label="维度">
          {DIMENSIONS.map(d => (
            <button key={d.id}
                    className={activeTab === d.id ? 'active' : ''}
                    onClick={() => setActiveTab(d.id)}>
              {d.zh}
              <span className="en">{d.en}</span>
            </button>
          ))}
        </nav>

        {list.length > 0 ? (
          <div className="feed">
            {list.map(s => (
              <FeedCard key={s.id} s={s}
                        showStamp={tweaks.stamp}
                        accent={tweaks.accent}
                        onOpen={() => navigate({ name: 'detail', id: s.id })}/>
            ))}
          </div>
        ) : (
          <EmptyDimension dim={DIMENSIONS.find(d => d.id === activeTab)}/>
        )}

        <div className="feed-foot">
          <span>May 2026</span>
          <span className="dotline"/>
          <span>{list.length.toString().padStart(2, '0')} 件</span>
        </div>

        <div className="collect-cta">
          <button onClick={() => setExported(true)}>
            {exported ? '已 · 收 入 图 鉴' : '导 出 · 分 享 此 册'}
          </button>
        </div>
      </div>
    </div>
  );
}

function FeedCard({ s, showStamp, accent, onOpen }) {
  return (
    <article className="card" onClick={onOpen}
             data-screen-label={`Specimen ${s.no}`}>
      <div className="plate" role="img" aria-label={`${s.title} placeholder`}>
        <PlateSVG kind={s.kind} palette={s.palette}/>
        <span className="corner">PLATE / {s.no.replace('No. ', '')}</span>
        <span className="corner r">[ {s.kind} · placeholder ]</span>
        {showStamp && <span className="stamp">{s.stamp}</span>}
      </div>

      <section className="swatches">
        <div className="bars" role="list">
          {s.palette.map((p, i) => (
            <span key={i} role="listitem" style={{ background: p.hex }}/>
          ))}
        </div>
        <div className="legend">
          {s.palette.map((p, i) => (
            <div key={i}>
              <span className="hex">{p.hex}</span>
              <span className="zh">{p.zh}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="meta">
        <div>
          <div className="ts">{s.date} &nbsp;·&nbsp; {s.time}</div>
          <div className="geo">{s.geo} &nbsp; · &nbsp; {s.place}</div>
        </div>
        <div className="tag" style={{ color: accent }}>{s.dimension}</div>
      </section>

      <section className="poem">
        <hr/>
        <p>{s.title.split('·').map((seg, i, arr) => (
          <React.Fragment key={i}>
            {seg}
            {i < arr.length - 1 && <span className="dot">·</span>}
          </React.Fragment>
        ))}</p>
      </section>
    </article>
  );
}

function EmptyDimension({ dim }) {
  return (
    <div style={{
      margin: '24px 26px 12px',
      padding: '48px 24px',
      borderTop: '1px solid var(--rule)',
      borderBottom: '1px solid var(--rule)',
      textAlign: 'center',
      fontFamily: '"Noto Serif SC", serif',
      color: 'var(--ink-mute)',
    }}>
      <div style={{
        fontFamily: '"EB Garamond", serif',
        fontStyle: 'italic',
        fontSize: 14,
        letterSpacing: '.1em',
        marginBottom: 10,
      }}>The {dim?.en} field is empty.</div>
      <div style={{ fontSize: 13, letterSpacing: '.22em' }}>
        — 尚未采集 {dim?.zh} 标本 —
      </div>
      <div style={{
        marginTop: 18,
        fontFamily: '"Caveat", cursive',
        fontSize: 20,
        color: 'var(--accent)',
        transform: 'rotate(-3deg)',
      }}>下次散步顺路收一件？</div>
    </div>
  );
}

function IOSHomeIndicator({ dark }) {
  return (
    <div style={{
      position: 'absolute',
      bottom: 8,
      left: '50%',
      transform: 'translateX(-50%)',
      width: 134,
      height: 5,
      borderRadius: 3,
      background: dark ? 'rgba(255,255,255,.55)' : 'rgba(0,0,0,.55)',
      zIndex: 20,
      pointerEvents: 'none',
    }}/>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
