import React from "react";
import { Eye, Type, BellRing, Sparkles, Smile, RefreshCw, Layers } from "lucide-react";

interface AccessibilitySettingsProps {
  fontSizeClass: "text-xs" | "text-sm" | "text-base" | "text-lg";
  setFontSizeClass: (fc: "text-xs" | "text-sm" | "text-base" | "text-lg") => void;
  visualHaptics: boolean;
  setVisualHaptics: (vh: boolean) => void;
  highContrast: boolean;
  setHighContrast: (hc: boolean) => void;
  guideBox: boolean;
  setGuideBox: (gb: boolean) => void;
}

export default function AccessibilitySettings({
  fontSizeClass,
  setFontSizeClass,
  visualHaptics,
  setVisualHaptics,
  highContrast,
  setHighContrast,
  guideBox,
  setGuideBox
}: AccessibilitySettingsProps) {
  return (
    <div className="p-6 rounded-2xl bg-slate-950 border border-slate-800 shadow-xl max-w-4xl mx-auto">
      
      {/* Title Header */}
      <div className="pb-4 border-b border-slate-800 mb-6">
        <h2 className="text-base font-extrabold text-slate-100 flex items-center gap-2">
          <Eye className="w-5 h-5 text-teal-400" />
          听障人士专享 · 全链路无障碍适配面板 (DHH Accessible Controls)
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          本产品在研发阶段专为听障用户提供辅助交互，在无音视障状态下由色彩、微震动、大字号字幕代偿。
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        
        {/* Style scale controls */}
        <div className="flex flex-col gap-6">
          
          {/* FontSize adjuster option */}
          <div className="flex flex-col gap-2">
            <label className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
              <Type className="w-4 h-4 text-sky-400" />
              1. 实时文本及字幕字号调节 (Font Scale Selection)
            </label>
            <p className="text-[11px] text-slate-500">
              增大视频挂载弹幕与中转信息的视觉面积，避免用眼过度。
            </p>

            <div className="grid grid-cols-4 gap-2 mt-2">
              {([
                { id: "text-xs", label: "标准 (XS)" },
                { id: "text-sm", label: "中等 (SM)" },
                { id: "text-base", label: "大号 (REGULAR)" },
                { id: "text-lg", label: "特大 (XLARGE)" }
              ] as const).map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setFontSizeClass(opt.id)}
                  className={`py-2 px-3 rounded-xl text-xs transition-all ${
                    fontSizeClass === opt.id
                      ? "bg-teal-600 text-white font-extrabold shadow-md"
                      : "bg-slate-900 text-slate-300 hover:bg-slate-850"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* High Contrast color setting */}
          <div className="flex items-start justify-between p-4 rounded-xl bg-slate-900/50 border border-slate-850 mt-2">
            <div className="flex-1 pr-4">
              <span className="text-xs font-bold text-slate-200 block">2. 极高对比度户外光照模式 (Outdoor Sight)</span>
              <p className="text-[10px] text-slate-500 mt-1">
                切换至全黑纯色底衬，降低彩色杂波，保障太阳光下手指轮廓和中文字幕依旧醒目。
              </p>
            </div>
            <button
              onClick={() => setHighContrast(!highContrast)}
              className={`w-12 h-6 flex items-center rounded-full p-1 transition-colors duration-300 ${
                highContrast ? "bg-teal-600 justify-end" : "bg-slate-800 justify-start"
              }`}
            >
              <span className="bg-white w-4 h-4 rounded-full shadow-md" />
            </button>
          </div>

        </div>

        {/* Dynamic compensations options */}
        <div className="flex flex-col gap-6">
          
          {/* Visual ringtone pulse toggle */}
          <div className="flex items-start justify-between p-4 rounded-xl bg-slate-900/50 border border-slate-850">
            <div className="flex-1 pr-4">
              <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <BellRing className="w-4 h-4 text-rose-400" />
                3. 新来电全方位呼吸灯视觉提醒 (Visual Ringtone Flash)
              </span>
              <p className="text-[10px] text-slate-500 mt-1">
                开启后，当有呼入信号时，网页视口周遭会亮起粉红色闪烁呼吸流，取代音响振铃发出预警。
              </p>
            </div>
            <button
              onClick={() => setVisualHaptics(!visualHaptics)}
              className={`w-12 h-6 flex items-center rounded-full p-1 transition-colors duration-300 ${
                visualHaptics ? "bg-teal-600 justify-end" : "bg-slate-800 justify-start"
              }`}
            >
              <span className="bg-white w-4 h-4 rounded-full shadow-md" />
            </button>
          </div>

          {/* Guiding alignment boundary boxes */}
          <div className="flex items-start justify-between p-4 rounded-xl bg-slate-900/50 border border-slate-850">
            <div className="flex-1 pr-4">
              <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-purple-400" />
                4. 摄像头手势对齐姿态引导框 (Skeleton Grid Guides)
              </span>
              <p className="text-[10px] text-slate-500 mt-1">
                在用户端视频渲染器中画出虚线手持位置边界，辅助在合理视野深度打出标准手势。
              </p>
            </div>
            <button
              onClick={() => setGuideBox(!guideBox)}
              className={`w-12 h-6 flex items-center rounded-full p-1 transition-colors duration-300 ${
                guideBox ? "bg-teal-600 justify-end" : "bg-slate-800 justify-start"
              }`}
            >
              <span className="bg-white w-4 h-4 rounded-full shadow-md" />
            </button>
          </div>

        </div>

      </div>

      <div className="mt-6 pt-4 border-t border-slate-900 flex items-center gap-2 text-[10px] font-mono text-teal-400">
        <Sparkles className="w-3.5 h-3.5" />
        <span>以上无障碍数据将缓存至 localState 中，全局无缝透传生效。</span>
      </div>

    </div>
  );
}
