// Map screen — stylized paper map of FFC area with specimen pins

function MapScreen({ navigate, accent }) {
  const [selected, setSelected] = React.useState(null);

  // Hand-positioned pins on the abstract paper map (percent of 360×620 canvas)
  // The first 5 specimens are in FFC; #4 苏州河 lives at the top as a callout
  const pinPositions = {
    'jl-brick':     { x: 52,  y: 44 },   // 巨鹿路
    'hs-leaf':      { x: 62,  y: 70 },   // 衡山路
    'wk-deco':      { x: 28,  y: 56 },   // 武康大楼
    'sz-fog':       { x: 58,  y: 14 },   // 苏州河 (north)
    'yk-wisteria':  { x: 45,  y: 62 },   // 永康路
    'af-awning':    { x: 38,  y: 38 },   // 安福路
  };

  return (
    <div className="screen map-screen" data-screen-label="Map">
      <div className="topbar">
        <button className="back" onClick={() => navigate({ name: 'feed' }, 'back')} aria-label="返回">
          <svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg>
        </button>
        <div className="title">
          地 · 图
          <em>FIELD MAP</em>
        </div>
        <button className="icn" aria-label="图层">
          <svg viewBox="0 0 24 24">
            <path d="M12 4l9 5-9 5-9-5 9-5z"/>
            <path d="M3 14l9 5 9-5"/>
          </svg>
        </button>
      </div>

      <div className="map-wrap">
        <div className="map-head">
          <h2>巨鹿路一带</h2>
          <div className="sub">Former French Concession &nbsp;·&nbsp; 6 specimens</div>
        </div>

        <span className="map-callout">17 — 22 MAY · MMXXVI</span>

        {/* Paper map */}
        <svg className="map-svg" viewBox="0 0 360 620"
             preserveAspectRatio="xMidYMid slice"
             xmlns="http://www.w3.org/2000/svg">

          {/* park blobs */}
          <ellipse className="park-blob" cx="200" cy="430" rx="42" ry="22"/>
          <ellipse className="park-blob" cx="70"  cy="280" rx="34" ry="22"/>

          {/* major curving roads */}
          <path className="street street-major"
                d="M -20 240 C 60 230, 180 250, 380 220"/>
          <path className="street street-major"
                d="M -10 380 C 80 380, 210 400, 380 380"/>
          <path className="street street-major"
                d="M -20 470 C 80 470, 220 480, 380 470"/>

          {/* diagonal 武康路 */}
          <path className="street street-minor"
                d="M 60 540 C 90 460, 110 380, 130 300 S 180 160, 220 80"/>

          {/* minor cross streets */}
          <path className="street street-minor" d="M 110 -10 L 100 640"/>
          <path className="street street-minor" d="M 200 -10 L 210 640"/>
          <path className="street street-minor" d="M 290 -10 L 280 640"/>

          {/* extra minor */}
          <path className="street street-minor" d="M -10 150 C 80 150, 220 160, 380 140"/>
          <path className="street street-minor" d="M -10 320 C 80 330, 220 320, 380 330"/>

          {/* river hint — 苏州河, top */}
          <path className="street"
                d="M -10 60 C 90 50, 200 80, 380 50"
                style={{ strokeWidth: 10, stroke: 'color-mix(in srgb, var(--ink-mute) 22%, transparent)' }}/>
          <text className="label-en" x="14" y="42">SŪZHŌU CREEK ↑</text>

          {/* street labels */}
          <text className="label"    x="156" y="232">巨 鹿 路</text>
          <text className="label-en" x="156" y="243">JULU RD</text>

          <text className="label"    x="150" y="376">长 乐 路</text>
          <text className="label-en" x="150" y="387">CHANGLE RD</text>

          <text className="label"    x="150" y="466">衡 山 路</text>
          <text className="label-en" x="150" y="477">HENGSHAN RD</text>

          <text className="label"    x="20"  y="146">安 福 路</text>
          <text className="label-en" x="20"  y="157">ANFU RD</text>

          <text className="label"    x="20"  y="316">永 康 路</text>
          <text className="label-en" x="20"  y="327">YONGKANG RD</text>

          <text className="label" transform="rotate(-58 120 340)" x="98" y="340">武 康 路</text>

          {/* compass */}
          <g transform="translate(326, 96)">
            <line x1="0" y1="-14" x2="0" y2="14" stroke="currentColor" opacity=".4"/>
            <line x1="-10" y1="0" x2="10" y2="0" stroke="currentColor" opacity=".4"/>
            <text className="compass" x="-3" y="-18">N</text>
          </g>
        </svg>

        {/* pins */}
        {SPECIMENS.map(s => {
          const p = pinPositions[s.id];
          if (!p) return null;
          return (
            <div key={s.id}
                 className={`map-pin ${selected === s.id ? 'active' : ''}`}
                 style={{ left: `${p.x}%`, top: `${p.y}%` }}
                 onClick={() => setSelected(s.id)}>
              <span className="dot" style={{ background: s.palette[0].hex }}/>
              <span className="pin-no">{s.no.replace('No. ', '')}</span>
            </div>
          );
        })}

        {/* preview sheet */}
        {selected && (() => {
          const s = SPECIMENS.find(x => x.id === selected);
          return (
            <div className="map-sheet"
                 onClick={() => navigate({ name: 'detail', id: s.id })}>
              <div className="thumb">
                <PlateSVG kind={s.kind} palette={s.palette}/>
              </div>
              <div className="info">
                <div className="title">{s.title}</div>
                <div className="sub">{s.no} &nbsp;·&nbsp; {s.place}</div>
                <div className="swatch-line">
                  {s.palette.map((p, i) => (
                    <span key={i} style={{ background: p.hex }}/>
                  ))}
                </div>
              </div>
              <span className="arrow">→</span>
            </div>
          );
        })()}
      </div>
    </div>
  );
}

Object.assign(window, { MapScreen });
