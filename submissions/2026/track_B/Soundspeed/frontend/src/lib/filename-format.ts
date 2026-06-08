// 文件名显示格式（场镜次 → 录音机文件名风格，如 Scene_1/Shot 1/Take 1 → 01_S1_T001）。
// 用户可在设置页配置，统一应用到所有显示场镜次的地方（History / Live 分隔条 / 底栏 / titlebar / 详情）。
// 纯前端显示偏好，存 localStorage。

// 单段格式：前缀 + 数字（可补零）。pad=0 表示不补零（用原数字）。
export interface SegFormat {
  prefix: string // 如 "Scene" / "Sc" / "" / "Shot" / "S" / "Take" / "T" / "Tk"
  pad: number // 补零到几位；0=不补零
}

export interface FileNameFormat {
  scene: SegFormat
  shot: SegFormat
  take: SegFormat
  sep: string // 段间分隔符："_" / "-" / " · " / " "
}

// 各段前缀候选（设置页下拉用）。
export const SCENE_PREFIXES = ["", "Sc", "Scene"] as const
export const SHOT_PREFIXES = ["", "S", "Sh", "Shot"] as const
export const TAKE_PREFIXES = ["T", "Tk", "Take", ""] as const
export const SEPARATORS = ["_", "-", " · ", " "] as const
export const PAD_OPTIONS = [0, 1, 2, 3] as const

// 默认：Sc1_S1_T001（补零只给 Take；Scene/Shot 不补零）。
export const DEFAULT_FILENAME_FORMAT: FileNameFormat = {
  scene: { prefix: "Sc", pad: 0 },
  shot: { prefix: "S", pad: 0 },
  take: { prefix: "T", pad: 3 },
  sep: "_",
}

// 几个开箱预设（设置页「预设」快选）。补零只用在 Take（Scene/Shot pad 固定 0）。
export const FILENAME_PRESETS: { label: string; value: FileNameFormat }[] = [
  {
    label: "Sc1_S1_T001",
    value: { scene: { prefix: "Sc", pad: 0 }, shot: { prefix: "S", pad: 0 }, take: { prefix: "T", pad: 3 }, sep: "_" },
  },
  {
    label: "1_S1_T001",
    value: { scene: { prefix: "", pad: 0 }, shot: { prefix: "S", pad: 0 }, take: { prefix: "T", pad: 3 }, sep: "_" },
  },
  {
    label: "Sc1-S1-T01",
    value: { scene: { prefix: "Sc", pad: 0 }, shot: { prefix: "S", pad: 0 }, take: { prefix: "T", pad: 2 }, sep: "-" },
  },
  {
    label: "Scene1 · Shot1 · Take1",
    value: { scene: { prefix: "Scene", pad: 0 }, shot: { prefix: "Shot", pad: 0 }, take: { prefix: "Take", pad: 0 }, sep: " · " },
  },
]

// 从 scene_code（"Scene_1" / "3A" / "1" 等）抽数字部分；抽不到则原样返回。
function digitsOf(code: string): string {
  const m = code.match(/\d+/)
  return m ? m[0] : code
}

function padNum(n: string | number, width: number): string {
  return width > 0 ? String(n).padStart(width, "0") : String(n)
}

function seg(prefix: string, value: string | number, pad: number): string {
  return prefix + padNum(value, pad)
}

// 把一条 take 的场/镜/次按格式拼成文件名串。缺失段跳过（不留空分隔）。
export function formatFileName(
  parts: { scene_code?: string | null; shot?: string | null; take_number?: number | null },
  fmt: FileNameFormat,
): string {
  const segs: string[] = []
  if (parts.scene_code) segs.push(seg(fmt.scene.prefix, digitsOf(parts.scene_code), fmt.scene.pad))
  if (parts.shot) segs.push(seg(fmt.shot.prefix, parts.shot, fmt.shot.pad))
  if (parts.take_number != null) segs.push(seg(fmt.take.prefix, parts.take_number, fmt.take.pad))
  return segs.join(fmt.sep)
}

// 设置页预览用的样例（Scene 1 / Shot 1 / Take 1）。
export const FILENAME_SAMPLE = { scene_code: "Scene_1", shot: "1", take_number: 1 }

// ── localStorage 持久化 ──
const LS_KEY = "soundspeed.filename_format"

export function loadFileNameFormat(): FileNameFormat {
  if (typeof localStorage === "undefined") return DEFAULT_FILENAME_FORMAT
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) return DEFAULT_FILENAME_FORMAT
    const parsed = JSON.parse(raw) as Partial<FileNameFormat>
    // 浅合并默认，容旧/缺字段。补零只用在 Take —— scene/shot.pad 强制归一为 0
    //（UI 不再暴露 Scene/Shot 补零，归一掉 localStorage 里的旧补零值）。
    return {
      scene: { prefix: parsed.scene?.prefix ?? DEFAULT_FILENAME_FORMAT.scene.prefix, pad: 0 },
      shot: { prefix: parsed.shot?.prefix ?? DEFAULT_FILENAME_FORMAT.shot.prefix, pad: 0 },
      take: { ...DEFAULT_FILENAME_FORMAT.take, ...parsed.take },
      sep: parsed.sep ?? DEFAULT_FILENAME_FORMAT.sep,
    }
  } catch {
    return DEFAULT_FILENAME_FORMAT
  }
}

export function saveFileNameFormat(fmt: FileNameFormat): void {
  if (typeof localStorage === "undefined") return
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(fmt))
  } catch {
    /* 忽略写失败（隐私模式等） */
  }
}
