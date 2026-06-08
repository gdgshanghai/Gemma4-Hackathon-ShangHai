// Detail screen — full specimen page

function DetailScreen({ specimen, navigate, accent }) {
  const s = specimen;
  if (!s) return null;

  // Stable pseudo-percentages from hex (so they don't reshuffle on re-render)
  const pcts = React.useMemo(() => {
    const seed = [...s.id].reduce((a, c) => a + c.charCodeAt(0), 0);
    const base = [38, 27, 21, 14];
    // small deterministic rotation
    const off = seed % 4;
    return base.map((b, i) => b + ((seed + i*3) % 5) - 2)
               .sort((a, b) => b - a);
  }, [s.id]);

  // RGB from hex helper
  const rgb = (hex) => {
    const h = hex.replace('#', '');
    const n = parseInt(h, 16);
    return `R${(n >> 16) & 255}  G${(n >> 8) & 255}  B${n & 255}`;
  };

  return (
    <div className="screen detail" data-screen-label={`Detail · ${s.no}`}>
      <div className="topbar">
        <button className="back" onClick={() => navigate({ name: 'feed' }, 'back')} aria-label="返回">
          <svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7" /></svg>
        </button>
        <div className="title">
          标 · 本
          <em>{s.no}</em>
        </div>
        <button className="icn" aria-label="分享">
          <svg viewBox="0 0 24 24">
            <path d="M12 3v12"/><path d="M8 7l4-4 4 4"/>
            <path d="M5 14v5a1 1 0 001 1h12a1 1 0 001-1v-5"/>
          </svg>
        </button>
      </div>

      <div className="scroll">
        <div className="hero">
          <PlateSVG kind={s.kind} palette={s.palette}/>
          <span className="corner">PLATE / {s.no.replace('No. ', '')}</span>
          <span className="corner r">[ {s.kind} · placeholder ]</span>
          <span className="stamp">{s.stamp}</span>
        </div>

        <div className="head">
          <h1>{s.title}</h1>
          <div className="meta-row">
            <span>{s.date} · {s.time}</span>
            <span className="geo">{s.geo}</span>
          </div>
          <div className="tag-row">
            <span style={{
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: 10, letterSpacing: '.18em',
              color: 'var(--ink-mute)',
            }}>{s.place}</span>
            <span className="dim" style={{ color: accent }}>{s.dimension}</span>
          </div>
        </div>

        <div className="section-label">
          <span className="zh">采 得 之 色</span>
          <span>extracted palette · 4</span>
        </div>
        <div className="swatch-list">
          {s.palette.map((p, i) => (
            <div key={i} className="swatch-row">
              <div className="chip" style={{ background: p.hex }}/>
              <div className="info">
                <span className="zh">{p.zh}</span>
                <span className="codes">{p.hex.toUpperCase()} &nbsp;·&nbsp; {rgb(p.hex)}</span>
              </div>
              <div className="pct">{pcts[i]}%</div>
            </div>
          ))}
        </div>

        <div className="section-label">
          <span className="zh">题 记</span>
          <span>field note</span>
        </div>
        <div className="notes">
          {(s.notes || DEFAULT_NOTES[s.kind] || DEFAULT_NOTES.brick).map((line, i) => (
            <p key={i}>{line}</p>
          ))}
          <div className="sig">— 行人 No. 042</div>
        </div>

        <div className="section-label">
          <span className="zh">同 行 标 本</span>
          <span>nearby</span>
        </div>
        <div className="nearby">
          {SPECIMENS.filter(x => x.id !== s.id).slice(0, 3).map(n => (
            <div key={n.id} className="mini" onClick={() => navigate({ name: 'detail', id: n.id })}>
              <PlateSVG kind={n.kind} palette={n.palette}/>
              <span className="label">{n.no.replace('No. ', '')}</span>
            </div>
          ))}
        </div>

        <div className="actions">
          <button>加 入 收 藏</button>
          <button className="primary">导 出 此 页</button>
        </div>
      </div>
    </div>
  );
}

// Default poetic notes per "kind" — used when a specimen has no custom notes
const DEFAULT_NOTES = {
  brick: [
    '下午四点四十二，骑车经过巨鹿路 821 号外墙，',
    '砖缝里有去年的落叶，被新雨打湿后又被风吹回来。',
    '红是被太阳晒过很多年的红，不是新墙的颜色。',
  ],
  leaf: [
    '梧桐的第一片黄落在咖啡店门口的木桌上。',
    '九点过一刻，光斜着进来，颜色比想象中暖。',
  ],
  facade: [
    '武康大楼转角，最后半小时的光打在奶油色的灰泥上。',
    '过路的人都举起手机，但风把广告牌掀得很响。',
  ],
  fog: [
    '清晨六点，苏州河上的雾像被人擦掉一半的画。',
    '远处的桥只剩一道墨线。',
  ],
  wisteria: [
    '永康路尽头那架紫藤晚祷似的，半垂在围墙外。',
    '颜色比纸上写的要旧一些，像是用过很多次的紫。',
  ],
  awning: [
    '安福路咖啡店的蓝布棚被昨夜的雨洗过，',
    '今早看上去比印象里更冷一些。',
  ],
};

Object.assign(window, { DetailScreen });
