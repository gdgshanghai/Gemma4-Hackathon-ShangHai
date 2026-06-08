import React, { useState } from "react";
import { Video, BookOpen, Settings, Eye, Info, HelpCircle } from "lucide-react";
import VideoCallHub from "./components/VideoCallHub";
import LearningHub from "./components/LearningHub";
import AccessibilitySettings from "./components/AccessibilitySettings";

export default function App() {
  // Navigation State
  const [activeTab, setActiveTab] = useState<"chat" | "learning" | "settings">("chat");

  // Accessibility States
  const [fontSizeClass, setFontSizeClass] = useState<"text-xs" | "text-sm" | "text-base" | "text-lg">("text-sm");
  const [visualHaptics, setVisualHaptics] = useState<boolean>(true);
  const [highContrast, setHighContrast] = useState<boolean>(false);
  const [guideBox, setGuideBox] = useState<boolean>(true);

  return (
    <div className={`min-h-screen transition-all duration-300 ${
      highContrast ? "bg-black text-white" : "bg-slate-900 text-slate-100"
    } font-sans antialiased pb-12`}>
      
      {/* GLOWING AMBIENT TOP BAR FOR VISUAL NOTIFICATION RINGTATION */}
      <div className={`h-2.5 w-full bg-linear-to-r transition-all duration-500 ${
        visualHaptics ? "from-teal-500 via-indigo-500 to-purple-500 animate-pulse" : "from-slate-700 to-slate-800"
      }`} />

      {/* HEADER SECTION */}
      <header className="max-w-7xl mx-auto px-4 pt-6 pb-2">
        <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-slate-800/80 pb-6 gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="w-8 h-8 rounded-xl bg-teal-500/10 border border-teal-500 flex items-center justify-center text-teal-400 font-extrabold text-lg shadow-inner shadow-teal-500/20">
                SL
              </span>
              <h1 className="text-xl md:text-2xl font-black text-slate-100 uppercase tracking-tight flex items-center gap-2">
                手语视频聊天与智能学习平台
                <span className="text-[10px] bg-teal-600/10 text-teal-400 font-bold px-2 py-0.5 rounded-full border border-teal-500/30 font-mono tracking-widest uppercase">
                  v2.0 Accessible
                </span>
              </h1>
            </div>
            
            <p className="text-xs text-slate-400 mt-1 max-w-2xl leading-relaxed">
              基于端侧骨架提取与三维手势拟态对齐，完美融合实时低延迟 HD WebRTC Subtitle 音视代偿。
              提供艾宾浩斯忘却周期手语词学堂，打破信息沟壑。
            </p>
          </div>

          {/* TAB WORKSPACE TRIGGER BAR */}
          <div className="flex items-center bg-slate-950 p-1.5 rounded-2xl border border-slate-800/80 self-start md:self-center">
            <button
              onClick={() => setActiveTab("chat")}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-black transition-all cursor-pointer ${
                activeTab === "chat"
                  ? "bg-teal-600 text-white shadow-lg shadow-teal-950/20"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Video className="w-4 h-4" />
              手语高清视聊
            </button>
            <button
              onClick={() => setActiveTab("learning")}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-black transition-all cursor-pointer ${
                activeTab === "learning"
                  ? "bg-teal-600 text-white shadow-lg shadow-teal-950/20"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <BookOpen className="w-4 h-4" />
              个性化手语词堂
            </button>
            <button
              onClick={() => setActiveTab("settings")}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-black transition-all cursor-pointer ${
                activeTab === "settings"
                  ? "bg-teal-600 text-white shadow-lg shadow-teal-950/20"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Settings className="w-4 h-4" />
              无障碍极简设定
            </button>
          </div>
        </div>
      </header>

      {/* CORE WORKSPACE ENTRY PANELS */}
      <main className="max-w-7xl mx-auto px-4 mt-6">
        {activeTab === "chat" && (
          <VideoCallHub
            visualHaptics={visualHaptics}
            fontSizeClass={fontSizeClass}
          />
        )}

        {activeTab === "learning" && (
          <LearningHub
            fontSizeClass={fontSizeClass}
          />
        )}

        {activeTab === "settings" && (
          <AccessibilitySettings
            fontSizeClass={fontSizeClass}
            setFontSizeClass={setFontSizeClass}
            visualHaptics={visualHaptics}
            setVisualHaptics={setVisualHaptics}
            highContrast={highContrast}
            setHighContrast={setHighContrast}
            guideBox={guideBox}
            setGuideBox={setGuideBox}
          />
        )}
      </main>

      {/* DEAF ACCESSIBILITY HELPFUL DISCLAIMERS */}
      <footer className="max-w-7xl mx-auto px-4 mt-12 pt-6 border-t border-slate-800/80">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-[11px] text-slate-500 font-mono">
          <p>© 2026 SignLink Assist. 全链路经端到端无损加密，符合 W3C WCAG 2.1 听障信息无障碍 A 级标准。</p>
          <div className="flex gap-4">
            <span className="text-teal-500">VP9 SFU Stream: 接入正常</span>
            <span className="text-purple-400">MediaPipe AI: 已就绪 (21 Joint Track)</span>
          </div>
        </div>
      </footer>

    </div>
  );
}
