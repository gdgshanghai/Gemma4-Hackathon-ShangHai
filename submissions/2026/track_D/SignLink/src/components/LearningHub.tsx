import React, { useState, useEffect } from "react";
import {
  BookOpen,
  Award,
  Zap,
  Sparkles,
  RefreshCw,
  Heart,
  CheckCircle,
  TrendingUp,
  AlertCircle,
  HelpCircle,
  Flame,
  ArrowRight
} from "lucide-react";
import { SignWord } from "../types";
import { SIGN_DATABASE } from "../utils/sign-gestures";
import CameraFeed from "./CameraFeed";

interface LearningHubProps {
  fontSizeClass: string;
}

export default function LearningHub({ fontSizeClass }: LearningHubProps) {
  // Database state linked with local storage
  const [lessons, setLessons] = useState<SignWord[]>([]);
  const [activeWord, setActiveWord] = useState<SignWord | null>(null);
  const [matchScore, setMatchScore] = useState<number>(0);
  const [practiceCompleted, setPracticeCompleted] = useState<boolean>(false);
  const [streakCount, setStreakCount] = useState<number>(5); // Default daily streak

  // Filter category state
  const [activeTab, setActiveTab] = useState<"all" | "greetings" | "daily" | "emergency">("all");

  // Load and store database
  useEffect(() => {
    const cachedData = localStorage.getItem("signlink_vocabulary");
    if (cachedData) {
      try {
        setLessons(JSON.parse(cachedData));
      } catch (e) {
        setLessons(SIGN_DATABASE);
      }
    } else {
      setLessons(SIGN_DATABASE);
      localStorage.setItem("signlink_vocabulary", JSON.stringify(SIGN_DATABASE));
    }
  }, []);

  // Filtered lists
  const filteredLessons = lessons.filter(
    (item) => activeTab === "all" || item.category === activeTab
  );

  // High interest list (Spaced Repetitive needs review under 65% memory state)
  const reviewDueLessons = lessons.filter((item) => item.memoryLevel < 65);

  const startPractice = (word: SignWord) => {
    setActiveWord(word);
    setMatchScore(0);
    setPracticeCompleted(false);
  };

  // Callback when match score changes from camera feed
  const handleMatchScore = (score: number) => {
    setMatchScore(score);
    // If similarity goes above 85%, mark as successful match
    if (score >= 82) {
      setPracticeCompleted(true);
    }
  };

  // Memory update with Spaced Repetition calculation
  const saveMemoryProgress = () => {
    if (!activeWord) return;

    const updated = lessons.map((l) => {
      if (l.id === activeWord.id) {
        // Boost memory score up to 100
        const newLevel = Math.min(100, Math.round(l.memoryLevel + (100 - l.memoryLevel) * 0.65));
        return {
          ...l,
          memoryLevel: newLevel,
          lastPracticed: new Date().toLocaleDateString()
        };
      }
      return l;
    });

    setLessons(updated);
    localStorage.setItem("signlink_vocabulary", JSON.stringify(updated));

    // Increase streak count
    setStreakCount((prev) => prev + 1);

    // Reset active practice card state
    setActiveWord(null);
    setPracticeCompleted(false);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      
      {/* LEFT: Target Vocabulary Lists & Spaced Repetition Decks (8 columns) */}
      <div className="lg:col-span-8 flex flex-col gap-6">
        
        {/* Daily Progress Tracker Stat widgets */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="p-4 rounded-2xl bg-gradient-to-br from-indigo-950 to-indigo-900 border border-indigo-500/30 shadow-md flex items-center justify-between">
            <div>
              <span className="text-[10px] text-indigo-300 font-mono tracking-wider">DAILY PRACTICE STREAK</span>
              <p className="text-2xl font-black text-white mt-1 flex items-center gap-1.5">
                <Flame className="w-6 h-6 text-orange-500 fill-orange-500 animate-bounce" />
                {streakCount} 天
              </p>
            </div>
            <span className="text-[10px] text-indigo-200 bg-indigo-900/50 px-2 py-1 rounded-lg">每日打卡</span>
          </div>

          <div className="p-4 rounded-2xl bg-gradient-to-br from-teal-950 to-teal-900 border border-teal-500/30 shadow-md flex items-center justify-between">
            <div>
              <span className="text-[10px] text-teal-300 font-mono tracking-wider">VOCABULARY MASTERED</span>
              <p className="text-2xl font-black text-white mt-1">
                {lessons.filter(l => l.memoryLevel >= 80).length} / {lessons.length}
              </p>
            </div>
            <span className="text-[10px] text-teal-200 bg-teal-900/50 px-2 py-1 rounded-lg">已熟练掌握</span>
          </div>

          <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 shadow-md flex items-center justify-between">
            <div>
              <span className="text-[10px] text-slate-400 font-mono tracking-wider">Spaced Repetition Needs</span>
              <p className="text-2xl font-black text-slate-200 mt-1 flex items-center gap-1.5">
                <AlertCircle className="w-5 h-5 text-indigo-400" />
                {reviewDueLessons.length} 词
              </p>
            </div>
            <span className="text-[10px] text-slate-300 bg-slate-900 px-2 py-1 rounded-lg">待复习</span>
          </div>
        </div>

        {/* Spaced Repetition Priority Panel */}
        {reviewDueLessons.length > 0 && (
          <div className="p-4 rounded-2xl bg-slate-950 border border-indigo-500/20 shadow-md">
            <div className="flex items-center gap-2 mb-3">
              <AlertCircle className="w-4 h-4 text-indigo-400" />
              <h3 className="text-xs font-mono font-bold text-slate-200 uppercase tracking-widest">
                艾宾浩斯忘却曲线：今日急需复习的词汇 (遗忘率高)
              </h3>
            </div>

            <div className="flex flex-wrap gap-2">
              {reviewDueLessons.map((item) => (
                <button
                  key={item.id}
                  onClick={() => startPractice(item)}
                  className="flex items-center gap-2 px-3 py-1.5 bg-indigo-950/40 hover:bg-indigo-950 border border-indigo-500/30 rounded-xl text-left transition-all"
                >
                  <span className="text-sm">{item.emoji}</span>
                  <div>
                    <p className="text-xs font-bold text-slate-200">{item.word}</p>
                    <p className="text-[9px] text-indigo-300">记忆剩: {item.memoryLevel}%</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Categories Tab navigation selector */}
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-teal-400" />
              标准手语个性化词汇库
            </h3>

            <div className="flex gap-1.5 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
              <button
                onClick={() => setActiveTab("all")}
                className={`px-3 py-1 rounded-lg transition-all ${activeTab === "all" ? "bg-teal-600 font-bold text-white" : "text-slate-400 hover:text-slate-200"}`}
              >
                全部 ({lessons.length})
              </button>
              <button
                onClick={() => setActiveTab("greetings")}
                className={`px-3 py-1 rounded-lg transition-all ${activeTab === "greetings" ? "bg-teal-600 font-bold text-white" : "text-slate-400 hover:text-slate-200"}`}
              >
                日常问候
              </button>
              <button
                onClick={() => setActiveTab("daily")}
                className={`px-3 py-1 rounded-lg transition-all ${activeTab === "daily" ? "bg-teal-600 font-bold text-white" : "text-slate-400 hover:text-slate-200"}`}
              >
                生活场景
              </button>
              <button
                onClick={() => setActiveTab("emergency")}
                className={`px-3 py-1 rounded-lg transition-all ${activeTab === "emergency" ? "bg-teal-600 font-bold text-white" : "text-slate-400 hover:text-slate-200"}`}
              >
                医疗急救
              </button>
            </div>
          </div>

          {/* Catalog grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredLessons.map((item) => (
              <div
                key={item.id}
                className="p-4 rounded-2xl bg-slate-950 border border-slate-800 hover:border-slate-700 transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-2xl">{item.emoji}</span>
                      <div>
                        <h4 className="text-sm font-extrabold text-slate-100">{item.word}</h4>
                        <p className="text-[10px] text-slate-400 font-mono">{item.pinyin} | {item.translation}</p>
                      </div>
                    </div>

                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      item.difficulty === "easy" ? "bg-emerald-950 text-emerald-400" : item.difficulty === "medium" ? "bg-amber-950 text-amber-400" : "bg-rose-950 text-rose-400"
                    }`}>
                      {item.difficulty === "easy" ? "简单" : item.difficulty === "medium" ? "中等" : "极难"}
                    </span>
                  </div>

                  <p className="text-xs text-slate-400 leading-relaxed bg-slate-900/50 p-2.5 rounded-xl border border-slate-900 mb-3">
                    {item.description}
                  </p>
                </div>

                <div className="flex items-center justify-between border-t border-slate-900 pt-3">
                  <div className="flex flex-col">
                    <span className="text-[9px] text-slate-500 font-mono uppercase">记忆维持熟练度</span>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <div className="w-20 bg-slate-900 h-1.5 rounded-full overflow-hidden border border-slate-800">
                        <div className="h-full bg-teal-500" style={{ width: `${item.memoryLevel}%` }} />
                      </div>
                      <span className="text-[10px] font-bold text-slate-300 font-mono">{item.memoryLevel}%</span>
                    </div>
                  </div>

                  <button
                    onClick={() => startPractice(item)}
                    className="px-3.5 py-1.5 bg-teal-600 hover:bg-teal-500 text-white rounded-xl text-xs font-bold transition-all flex items-center gap-1 shadow-md shadow-teal-950/20"
                  >
                    练习
                    <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* RIGHT: Active Gesture Interactive Practice Arena (4 columns) */}
      <div className="lg:col-span-4 p-5 rounded-2xl bg-slate-950 border border-slate-800 shadow-xl flex flex-col gap-5">
        <div className="pb-3 border-b border-slate-800">
          <h3 className="text-sm font-extrabold text-slate-200 flex items-center gap-2">
            <Award className="w-4 h-4 text-purple-400 animate-pulse" />
            AI 骨骼姿态配准评测沙盒
          </h3>
          <p className="text-[11px] text-slate-400">摄像头开启后，MediaPipe 在本地评估对齐角度</p>
        </div>

        {activeWord ? (
          <div className="flex flex-col gap-4">
            
            {/* Target Display Card */}
            <div className="p-4 rounded-2xl bg-indigo-950/30 border border-indigo-500/20 flex items-center justify-between">
              <div>
                <span className="text-[9px] font-mono text-indigo-300">PRACTICING NOW</span>
                <h4 className="text-base font-extrabold text-white mt-0.5">{activeWord.word} ({activeWord.translation})</h4>
                <p className="text-xs text-slate-300 mt-1">{activeWord.pinyin}</p>
              </div>
              <span className="text-4xl animate-bounce">{activeWord.emoji}</span>
            </div>

            {/* Practice Camera Feed block */}
            <div className="relative">
              <CameraFeed
                activeWord={activeWord}
                onMatchScore={handleMatchScore}
              />
            </div>

            {/* Description reference text */}
            <div className="p-3 bg-slate-900 border border-slate-800 rounded-xl">
              <span className="text-[9px] text-slate-500 font-mono uppercase font-bold">标准手势提示 (CSL 指南)</span>
              <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                {activeWord.landmarksDescription}
              </p>
            </div>

            {/* Match Rating Progress feedback */}
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-center">
              <span className="text-[10px] text-slate-400 font-mono block">实时配准偏差对齐度</span>
              
              <div className="flex items-center justify-center gap-2 mt-2">
                <span className="text-2xl font-black font-mono text-teal-400">{matchScore}%</span>
                <span className="text-xs font-semibold text-slate-300">/ 82% 目标分</span>
              </div>

              <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden mt-2 border border-slate-800">
                <div
                  className={`h-full transition-all duration-300 ${matchScore >= 82 ? "bg-emerald-500" : "bg-teal-500"}`}
                  style={{ width: `${matchScore}%` }}
                />
              </div>

              {practiceCompleted ? (
                <div className="mt-4 p-2 bg-emerald-950/60 text-emerald-300 text-xs font-bold rounded-xl border border-emerald-500/30 flex items-center justify-center gap-1.5 animate-bounce">
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                  🎯 姿态匹配完美！(得分 {matchScore}%)
                </div>
              ) : (
                <div className="mt-4 p-2 bg-slate-950/80 text-slate-400 text-xs rounded-xl flex items-center justify-center gap-1.5 max-w-sm mx-auto">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-teal-400" />
                  请模仿上述提示调整手指，等待对齐对准...
                </div>
              )}
            </div>

            {/* Confirm complete action button */}
            <button
              onClick={saveMemoryProgress}
              disabled={!practiceCompleted}
              className={`w-full py-3 rounded-xl text-xs font-black transition-all flex items-center justify-center gap-1.5 shadow-lg ${
                practiceCompleted
                  ? "bg-gradient-to-r from-emerald-600 to-teal-600 text-white hover:from-emerald-500 hover:to-teal-500 cursor-pointer"
                  : "bg-slate-800 text-slate-500 cursor-not-allowed"
              }`}
            >
              完成并加入记忆库
            </button>

            <button
              onClick={() => setActiveWord(null)}
              className="w-full text-center text-xs text-slate-500 hover:text-slate-400 py-1"
            >
              取消练习
            </button>

          </div>
        ) : (
          <div className="flex flex-col items-center justify-center text-center p-8 h-[360px] text-slate-500 bg-slate-900/40 rounded-2xl border border-dashed border-slate-800">
            <BookOpen className="w-10 h-10 text-slate-700 mb-3" />
            <p className="text-xs font-bold text-slate-400">词标对齐检测器闲置中</p>
            <p className="text-[10px] text-slate-500 max-w-xs mt-1.5 leading-relaxed">
              请从左侧词库目录中任选一个词汇点击【练习】。即可激活 MediaPipe 本端骨架投射，学习精准打出手势。
            </p>
          </div>
        )}

      </div>

    </div>
  );
}
