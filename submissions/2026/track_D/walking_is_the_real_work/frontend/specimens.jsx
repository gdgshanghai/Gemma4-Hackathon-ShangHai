// Specimen data + placeholder plate SVG renderer.
// Each specimen is a "page" in the field guide.

const SPECIMENS = [
  {
    id: 'jl-brick',
    no: 'No. 0237',
    title: '巨鹿路·落叶与单车砖红',
    dimension: '02 视觉维度',
    place: 'JÙLÙ ROAD',
    geo: '31.2168° N   121.4571° E',
    date: 'Friday, 17 May 2026',
    time: '16:42',
    stamp: '采',
    kind: 'brick',
    palette: [
      { hex: '#8C2D19', zh: '砖 红' },
      { hex: '#A39E93', zh: '暮 灰' },
      { hex: '#D9C5A0', zh: '米 黄' },
      { hex: '#3E2E22', zh: '深 褐' },
    ],
  },
  {
    id: 'hs-leaf',
    no: 'No. 0238',
    title: '衡山路·梧桐第一片黄',
    dimension: '02 视觉维度',
    place: 'HÉNGSHĀN ROAD',
    geo: '31.2034° N   121.4498° E',
    date: 'Saturday, 18 May 2026',
    time: '09:12',
    stamp: '叶',
    kind: 'leaf',
    palette: [
      { hex: '#C9A24E', zh: '初 黄' },
      { hex: '#6B5A2E', zh: '苔 褐' },
      { hex: '#E8DFC4', zh: '麻 白' },
      { hex: '#2F3A1F', zh: '墨 绿' },
    ],
  },
  {
    id: 'wk-deco',
    no: 'No. 0239',
    title: '武康大楼·黄昏奶油色',
    dimension: '02 视觉维度',
    place: 'WǓKĀNG MANSION',
    geo: '31.2099° N   121.4365° E',
    date: 'Sunday, 19 May 2026',
    time: '18:36',
    stamp: '昏',
    kind: 'facade',
    palette: [
      { hex: '#E6C58A', zh: '奶 油' },
      { hex: '#C97B4B', zh: '日 暮' },
      { hex: '#6E3B26', zh: '赭 石' },
      { hex: '#2A2118', zh: '夜 至' },
    ],
  },
  {
    id: 'sz-fog',
    no: 'No. 0240',
    title: '苏州河·晨雾灰青',
    dimension: '02 视觉维度',
    place: 'SŪZHŌU CREEK',
    geo: '31.2410° N   121.4691° E',
    date: 'Monday, 20 May 2026',
    time: '06:08',
    stamp: '雾',
    kind: 'fog',
    palette: [
      { hex: '#8B97A0', zh: '雾 青' },
      { hex: '#C4CBCE', zh: '霜 灰' },
      { hex: '#4D585F', zh: '远 山' },
      { hex: '#DCDBD3', zh: '茧 白' },
    ],
  },
  {
    id: 'yk-wisteria',
    no: 'No. 0241',
    title: '永康路·紫藤晚祷',
    dimension: '02 视觉维度',
    place: 'YǑNGKĀNG ROAD',
    geo: '31.2103° N   121.4541° E',
    date: 'Tuesday, 21 May 2026',
    time: '19:15',
    stamp: '藤',
    kind: 'wisteria',
    palette: [
      { hex: '#6F5A8C', zh: '紫 藤' },
      { hex: '#C7B8D6', zh: '霭 紫' },
      { hex: '#3E3450', zh: '夜 紫' },
      { hex: '#E5D6E5', zh: '残 樱' },
    ],
  },
  {
    id: 'af-awning',
    no: 'No. 0242',
    title: '安福路·咖啡店外的蓝',
    dimension: '02 视觉维度',
    place: 'ĀNFÚ ROAD',
    geo: '31.2138° N   121.4452° E',
    date: 'Wednesday, 22 May 2026',
    time: '11:24',
    stamp: '蓝',
    kind: 'awning',
    palette: [
      { hex: '#2F4A6E', zh: '雨 蓝' },
      { hex: '#B9C7D6', zh: '海 雾' },
      { hex: '#1A2434', zh: '深 蓝' },
      { hex: '#D5BFA2', zh: '麻 绳' },
    ],
  },
];

// ── PlateSVG ──────────────────────────────────────────────────────────
// A tasteful, abstract placeholder generated from the specimen's
// palette + a "kind" hint. No illustration; just bands / blotches / grain.
function PlateSVG({ kind, palette }) {
  const [c1, c2, c3, c4] = palette.map(p => p.hex);
  const uid = React.useId().replace(/:/g, '_');
  const filterId = `grain_${uid}`;
  const vgId     = `vg_${uid}`;
  const noiseId  = `noise_${uid}`;

  const defs = (
    <defs>
      <filter id={noiseId}>
        <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch"/>
        <feColorMatrix values="0 0 0 0 0.15  0 0 0 0 0.10  0 0 0 0 0.08  0 0 0 0.40 0"/>
      </filter>
      <filter id={filterId}>
        <feTurbulence type="fractalNoise" baseFrequency="1.7" numOctaves="2" stitchTiles="stitch"/>
        <feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.20 0"/>
      </filter>
      <linearGradient id={vgId} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0"  stopColor="#000" stopOpacity=".05"/>
        <stop offset=".55" stopColor="#000" stopOpacity="0"/>
        <stop offset="1"  stopColor="#000" stopOpacity=".40"/>
      </linearGradient>
    </defs>
  );

  // Each "kind" composes a different ground beneath the same grain + vignette.
  let ground = null;

  if (kind === 'brick') {
    const brickId = `brick_${uid}`;
    const brick2Id = `brick2_${uid}`;
    ground = (
      <React.Fragment>
        <defs>
          <pattern id={brickId} width="120" height="42" patternUnits="userSpaceOnUse">
            <rect width="120" height="42" fill={c1}/>
            <rect width="120" height="42" filter={`url(#${noiseId})`}/>
            <rect width="120" height="2" fill={c4} opacity=".55"/>
            <rect y="40" width="120" height="2" fill={c4} opacity=".55"/>
            <rect x="58" width="2" height="42" fill={c4} opacity=".55"/>
          </pattern>
          <pattern id={brick2Id} width="120" height="42" patternUnits="userSpaceOnUse" patternTransform="translate(60,42)">
            <rect width="120" height="42" fill={c1} opacity=".92"/>
            <rect width="120" height="2" fill={c4} opacity=".55"/>
            <rect y="40" width="120" height="2" fill={c4} opacity=".55"/>
            <rect x="58" width="2" height="42" fill={c4} opacity=".55"/>
          </pattern>
        </defs>
        <rect width="600" height="600" fill={`url(#${brickId})`}/>
        <g transform="translate(0,42)"><rect width="600" height="600" fill={`url(#${brick2Id})`}/></g>
        <ellipse cx="120" cy="180" rx="180" ry="120" fill={c2} opacity=".22"/>
        <ellipse cx="480" cy="430" rx="220" ry="160" fill={c4} opacity=".26"/>
        <ellipse cx="320" cy="520" rx="260" ry="80"  fill={c3} opacity=".18"/>
      </React.Fragment>
    );
  } else if (kind === 'leaf') {
    ground = (
      <React.Fragment>
        <rect width="600" height="600" fill={c1}/>
        <g opacity=".70">
          {Array.from({length: 18}).map((_, i) => (
            <rect key={i} x={-50 + i*40} y="-50" width="14" height="800" fill={c2}
                  transform="rotate(-22 300 300)" opacity={0.12 + (i%5)*0.06}/>
          ))}
        </g>
        <ellipse cx="380" cy="220" rx="260" ry="160" fill={c3} opacity=".30"/>
        <ellipse cx="120" cy="460" rx="200" ry="140" fill={c4} opacity=".24"/>
      </React.Fragment>
    );
  } else if (kind === 'facade') {
    // Vertical art-deco bands
    ground = (
      <React.Fragment>
        <rect width="600" height="600" fill={c1}/>
        {Array.from({length: 9}).map((_, i) => (
          <rect key={i} x={i*70} y="0" width="34" height="600"
                fill={i%2 ? c2 : c3} opacity={i%2 ? .35 : .22}/>
        ))}
        <rect x="0" y="0" width="600" height="120" fill={c4} opacity=".18"/>
        <rect x="0" y="420" width="600" height="180" fill={c3} opacity=".28"/>
        <ellipse cx="500" cy="80" rx="240" ry="110" fill={c2} opacity=".28"/>
      </React.Fragment>
    );
  } else if (kind === 'fog') {
    // Horizontal bands of fog
    ground = (
      <React.Fragment>
        <rect width="600" height="600" fill={c2}/>
        <rect y="0"   width="600" height="200" fill={c4} opacity=".35"/>
        <rect y="180" width="600" height="120" fill={c1} opacity=".40"/>
        <rect y="300" width="600" height="160" fill={c2} opacity=".55"/>
        <rect y="460" width="600" height="140" fill={c3} opacity=".70"/>
        <ellipse cx="200" cy="320" rx="320" ry="60" fill={c3} opacity=".25"/>
        <ellipse cx="480" cy="380" rx="260" ry="50" fill={c3} opacity=".30"/>
      </React.Fragment>
    );
  } else if (kind === 'wisteria') {
    // Vertical hanging dots
    ground = (
      <React.Fragment>
        <rect width="600" height="600" fill={c2}/>
        <rect width="600" height="600" fill={c3} opacity=".35"/>
        {Array.from({length: 9}).map((_, col) =>
          Array.from({length: 14}).map((_, row) => {
            const x = 40 + col*65 + (row%2)*12;
            const y = 30 + row*42;
            const r = 8 + ((col+row)%4);
            return <circle key={`${col}-${row}`} cx={x} cy={y} r={r}
                          fill={(row+col)%3===0 ? c1 : c4} opacity={.25 + (row%4)*0.08}/>;
          })
        )}
        <rect x="0" y="420" width="600" height="200" fill={c4} opacity=".30"/>
      </React.Fragment>
    );
  } else if (kind === 'awning') {
    // Wide vertical bands like a striped awning
    ground = (
      <React.Fragment>
        <rect width="600" height="600" fill={c2}/>
        {Array.from({length: 6}).map((_, i) => (
          <rect key={i} x={i*100} y="0" width="100" height="600"
                fill={i%2 ? c1 : c2} opacity={i%2 ? .92 : .25}/>
        ))}
        <rect x="0" y="0" width="600" height="60" fill={c3} opacity=".35"/>
        <rect x="0" y="440" width="600" height="160" fill={c3} opacity=".22"/>
        <ellipse cx="300" cy="540" rx="220" ry="60" fill={c4} opacity=".25"/>
      </React.Fragment>
    );
  }

  return (
    <svg viewBox="0 0 600 600" preserveAspectRatio="xMidYMid slice"
         xmlns="http://www.w3.org/2000/svg">
      {defs}
      {ground}
      <rect width="600" height="600" filter={`url(#${filterId})`}/>
      <rect width="600" height="600" fill={`url(#${vgId})`}/>
    </svg>
  );
}

Object.assign(window, { SPECIMENS, PlateSVG });
