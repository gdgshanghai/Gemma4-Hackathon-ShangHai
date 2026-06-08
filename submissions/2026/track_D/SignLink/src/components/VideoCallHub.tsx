import React, { useState, useEffect, useRef } from "react";
import {
  Phone,
  PhoneOff,
  Video,
  VideoOff,
  MessageSquare,
  Send,
  Smile,
  Zap,
  Activity,
  User,
  Sparkles,
  Volume2,
  Tv,
  Maximize2,
  BellRing,
  Award
} from "lucide-react";
import CameraFeed from "./CameraFeed";
import { Message, SignWord } from "../types";
import { SIGN_DATABASE } from "../utils/sign-gestures";

interface VideoCallHubProps {
  visualHaptics: boolean;
  fontSizeClass: string;
}

export default function VideoCallHub({ visualHaptics, fontSizeClass }: VideoCallHubProps) {
  // Call state
  const [callState, setCallState] = useState<"idle" | "ringing" | "connected">("idle");
  const [micActive, setMicActive] = useState(true);
  const [videoActive, setVideoActive] = useState(true);

  // Chat/Messages states
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "m0",
      sender: "system",
      text: "欢迎使用 SignLink 高清手语通话系统。对方已上线，您可以启动一键视频通话。",
      timestamp: "09:00"
    }
  ]);
  const [inputText, setInputText] = useState("");

  // Subtitles overlying the remote stream
  const [subtitle, setSubtitle] = useState<string>("");

  // Network metrics state for low-latency feedback
  const [metrics, setMetrics] = useState({
    latencyMs: 14,
    fps: 60,
    resolution: "1920 × 1080 (HD)",
    bitrateKbps: 4820,
    packetLoss: 0.0,
    codec: "VP9 / Opus (SFU Mode)"
  });

  // Floating emojis on stream
  const [floatingEmojis, setFloatingEmojis] = useState<{ id: string; emoji: string; x: number; y: number }[]>([]);

  // Trigger words to simulate gesture detection
  const [selectedSimulatedWord, setSelectedSimulatedWord] = useState<string>("");

  // Simulated peer signing animation loop
  const [peerPose, setPeerPose] = useState<"holding" | "signing_hello" | "signing_thanks" | "signing_love">("holding");

  // Visual ringing pulse toggle
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (callState === "ringing") {
      interval = setInterval(() => {
        // Rings back & forth
      }, 500);
    }
    return () => clearInterval(interval);
  }, [callState]);

  // Network statistics fluctuations simulation
  useEffect(() => {
    if (callState !== "connected") return;

    const interval = setInterval(() => {
      setMetrics((prev) => ({
        ...prev,
        latencyMs: Math.max(9, Math.min(18, Math.round(prev.latencyMs + (Math.random() - 0.5) * 3))),
        bitrateKbps: Math.max(4200, Math.min(5200, Math.round(prev.bitrateKbps + (Math.random() - 0.5) * 150))),
        fps: Math.random() > 0.95 ? 59 : 60
      }));
    }, 2000);

    return () => clearInterval(interval);
  }, [callState]);

  // Handle incoming call mockup trigger
  const triggerIncomingCall = () => {
    setCallState("ringing");
    const audio = new Audio(); // optional fallback, but visually alerts user more
    setMessages((prev) => [
      ...prev,
      {
        id: `sys-${Date.now()}`,
        sender: "system",
        text: "⚡ 收到来自 '梅 (高级手语翻译专家)' 的低延迟视频通话呼叫...",
        timestamp: getLocalTimeString()
      }
    ]);
  };

  const handleAcceptCall = () => {
    setCallState("connected");
    setPeerPose("holding");
    setMessages((prev) => [
      ...prev,
      {
         id: `accept-${Date.now()}`,
         sender: "system",
         text: "🤝 通话已建立。MediaPipe 识别器已开启，视频正在通过 SFU 边缘中转。",
         timestamp: getLocalTimeString()
      }
    ]);

    // Simulated warm greeting from remote specialist after 1 second
    setTimeout(() => {
      setPeerPose("signing_hello");
      setSubtitle("【手语翻译-梅】: 嗨，你好！很高兴和您交流。");
      setMessages((prev) => [
        ...prev,
        {
          id: `p0-${Date.now()}`,
          sender: "peer",
          text: "嗨，你好！很高兴和您交流。",
          timestamp: getLocalTimeString(),
          isGesture: true,
          gestureWord: "你好"
        }
      ]);
    }, 1800);

    setTimeout(() => {
      setPeerPose("holding");
    }, 4500);
  };

  const handleDeclineCall = () => {
    setCallState("idle");
    setPeerPose("holding");
    setSubtitle("");
  };

  // Helper local time getter
  const getLocalTimeString = () => {
    const d = new Date();
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
  };

  // Chat message send handler
  const handleSendMessage = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputText.trim()) return;

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      sender: "self",
      text: inputText,
      timestamp: getLocalTimeString()
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText("");

    // Simulated responsive feedback from peer if call is connected
    if (callState === "connected") {
      setTimeout(() => {
        setPeerPose("signing_thanks");
        setSubtitle("【手语翻译-梅】: 收到！谢谢您的消息。");
        setMessages((prev) => [
          ...prev,
          {
            id: `p-${Date.now()}`,
            sender: "peer",
            text: "收到！非常感谢您。",
            timestamp: getLocalTimeString(),
            isGesture: true,
            gestureWord: "谢谢"
          }
        ]);
      }, 1500);

      setTimeout(() => {
        setPeerPose("holding");
      }, 4000);
    }
  };

  // Simulate hand sign gesture trigger on user's local side
  const handlePerformLocalGesture = (wordId: string) => {
    const word = SIGN_DATABASE.find(w => w.id === wordId);
    if (!word) return;

    setSelectedSimulatedWord(wordId);

    // After 1 sec, output translated text back onto chat
    setTimeout(() => {
      const translatedMessage: Message = {
        id: `g-${Date.now()}`,
        sender: "self",
        text: `【AI 手语转换】: ${word.word} (${word.translation})`,
        timestamp: getLocalTimeString(),
        isGesture: true,
        gestureWord: word.word
      };

      setMessages((prev) => [...prev, translatedMessage]);
      setSelectedSimulatedWord("");

      // Trigger floating emoji particle effect
      triggerFloatingEmoji(word.emoji);

      // Peer responds back
      if (callState === "connected") {
        setTimeout(() => {
          if (wordId === "iloveyou") {
            setPeerPose("signing_love");
            setSubtitle("【手语翻译-梅】: 同样祝福你！🤟");
            triggerFloatingEmoji("❤️");
          } else if (wordId === "hello") {
            setPeerPose("signing_hello");
            setSubtitle("【手语翻译-梅】: 你好，请问有什么可以帮您？");
          } else {
            setPeerPose("signing_thanks");
            setSubtitle("【手语翻译-梅】: 你的手势打得非常规范，点赞！👍");
          }
        }, 1200);

        setTimeout(() => {
          setPeerPose("holding");
        }, 4500);
      }
    }, 1000);
  };

  // Triggers visual emoji particles floating on screen
  const triggerFloatingEmoji = (emoji: string) => {
    const newEmojis = Array.from({ length: 8 }).map((_, i) => ({
      id: `${Date.now()}-${i}`,
      emoji,
      x: 20 + Math.random() * 60, // Left percentage
      y: 80 // Start from bottom of local video
    }));

    setFloatingEmojis((prev) => [...prev, ...newEmojis]);

    // Animate up and disappear
    setTimeout(() => {
      setFloatingEmojis((prev) => prev.filter(e => !newEmojis.some(ne => ne.id === e.id)));
    }, 2800);
  };

  return (
    <div className={`grid grid-cols-1 lg:grid-cols-12 gap-6 items-start ${visualHaptics && callState === "ringing" ? "ring-8 ring-rose-500 animate-pulse rounded-2xl" : ""}`}>
      
      {/* Visual ringtone overlay when ringing */}
      {callState === "ringing" && (
        <div className="lg:col-span-12 bg-rose-500 text-white font-bold p-4 rounded-xl flex items-center justify-between shadow-lg animate-bounce z-20">
          <div className="flex items-center gap-3">
            <BellRing className="w-6 h-6 animate-spin" />
            <div>
              <p className="text-sm">【视听融合提醒】收到来自 '高级手语翻译 - 梅' 的高清视频聊天邀请</p>
              <p className="text-xs text-rose-100 font-normal">系统正在以全屏闪烁振动代偿听觉铃声</p>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleAcceptCall}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-sm transition-colors flex items-center gap-1.5 font-bold shadow-md"
            >
              <Phone className="w-4 h-4" /> 接听 Call
            </button>
            <button
              onClick={handleDeclineCall}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm transition-colors flex items-center gap-1.5 font-normal"
            >
              拒接
            </button>
          </div>
        </div>
      )}

      {/* LEFT: Video Streams (8 columns) */}
      <div className="lg:col-span-8 flex flex-col gap-4">
        
        {/* Streams Container */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          
          {/* USER FEED (Local) */}
          <div className="flex flex-col gap-2">
            <div className="relative">
              <CameraFeed
                activeWord={null}
                onMatchScore={() => {}}
                selectedMockWordId={selectedSimulatedWord}
              />

              {/* Float emoji rendering over camera view */}
              <div className="absolute inset-0 pointer-events-none overflow-hidden">
                {floatingEmojis.map((e) => (
                  <span
                    key={e.id}
                    className="absolute text-5xl transition-all duration-[2500ms] ease-out animate-display-fade"
                    style={{
                      left: `${e.x}%`,
                      bottom: "10%",
                      transform: `translateY(-300px) scale(${1.5 + Math.random()})`,
                      opacity: 0
                    }}
                  >
                    {e.emoji}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* PEER FEED (Remote Specialist "Mei") */}
          <div className="flex flex-col gap-2">
            <div className="relative w-full aspect-video rounded-2xl overflow-hidden bg-slate-900 border border-slate-700 shadow-xl flex items-center justify-center group">
              
              {callState === "connected" ? (
                <div className="absolute inset-0 w-full h-full bg-slate-900">
                  {/* High Quality Video placeholder or simulation drawing */}
                  <div className="absolute inset-0 flex items-center justify-center">
                    {/* Hand joint coordinates simulation for "Mei" */}
                    <div className="text-center text-slate-100 flex flex-col items-center justify-center p-6 h-full w-full relative bg-radial from-slate-800 to-slate-950">
                      
                      {/* Avatar placeholder with gesture states */}
                      <div className="w-16 h-16 rounded-full bg-indigo-600/30 ring-4 ring-indigo-500/80 flex items-center justify-center mb-2 animate-pulse relative">
                        <User className="w-8 h-8 text-indigo-400" />
                        <span className="absolute -bottom-1 -right-1 bg-emerald-500 w-4.5 h-4.5 rounded-full border-2 border-slate-900 flex items-center justify-center text-[8px] font-bold text-slate-950">
                          HD
                        </span>
                      </div>
                      
                      <p className="text-xs font-semibold text-slate-300">高级手语专家-梅 (Mei)</p>
                      
                      {/* Interactive dynamic skeletal overlay of the signing user "Mei" */}
                      <div className="mt-4 flex flex-col items-center gap-1.5 p-3 rounded-lg bg-slate-950/80 border border-indigo-500/30 max-w-xs">
                        <div className="flex items-center gap-1 text-[11px] font-mono text-indigo-400">
                          <Activity className="w-3.5 h-3.5 text-indigo-500 animate-pulse" />
                          <span>远程肢体语义流: {peerPose.toUpperCase()}</span>
                        </div>
                        
                        <p className="text-xs text-slate-400 text-center leading-relaxed italic">
                          {peerPose === "holding" && "👋 正双手交叠，带着微笑专注倾听您的手势..."}
                          {peerPose === "signing_hello" && "双指合拢并拢掌心微弯 ——【正在比划: 你好】"}
                          {peerPose === "signing_thanks" && "右手拇指微曲，小指低头 ——【正在比划: 谢谢】"}
                          {peerPose === "signing_love" && "小指大拇指食指外翻 ——【正在比划: 我爱你】"}
                        </p>

                        {/* Interactive skeleton vector representation */}
                        <div className="flex items-center justify-center h-20 w-32 border border-slate-800 rounded bg-slate-900 mt-2 relative overflow-hidden">
                          {peerPose === "signing_hello" && (
                            <svg className="w-full h-full stroke-indigo-400 stroke-2 fill-none animate-pulse">
                              <circle cx="64" cy="20" r="8" />
                              <line x1="64" y1="28" x2="64" y2="60" />
                              <path d="M 64,36 C 85,25 90,10 95,8" />
                              <path d="M 64,36 C 45,36 40,55 35,65" />
                            </svg>
                          )}
                          {peerPose === "signing_thanks" && (
                            <svg className="w-full h-full stroke-teal-400 stroke-2 fill-none animate-pulse">
                              <circle cx="64" cy="20" r="8" />
                              <line x1="64" y1="28" x2="64" y2="60" />
                              <path d="M 64,36 C 85,36 80,60 90,65" />
                              <path d="M 64,36 C 40,20 30,12 25,12" strokeWidth="3" />
                            </svg>
                          )}
                          {peerPose === "signing_love" && (
                            <svg className="w-full h-full stroke-pink-400 stroke-3 fill-none animate-pulse">
                              <circle cx="64" cy="20" r="8" />
                              <line x1="64" y1="28" x2="64" y2="60" />
                              <path d="M 64,36 C 90,10 95,15 99,8" />
                              <path d="M 64,36 C 30,10 25,15 21,8" />
                            </svg>
                          )}
                          {peerPose === "holding" && (
                            <svg className="w-full h-full stroke-slate-500 stroke-2 fill-none">
                              <circle cx="64" cy="20" r="8" />
                              <line x1="64" y1="28" x2="64" y2="60" />
                              <path d="M 64,36 C 75,45 80,55 85,60" />
                              <path d="M 64,36 C 53,45 48,55 43,60" />
                            </svg>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Remote oversized overlay subtitles for deaf user accessibility */}
                  {subtitle && (
                    <div className="absolute inset-x-4 bottom-4 bg-slate-950/85 backdrop-blur-md rounded-xl p-3 border border-indigo-500/50 text-center animate-fade-in z-10 shadow-lg">
                      <p className="text-sm font-semibold text-emerald-400 mb-0.5 flex items-center justify-center gap-1">
                        <Tv className="w-3.5 h-3.5" /> 实时手语字幕翻译器
                      </p>
                      <p className="text-base md:text-lg font-bold text-white tracking-wide">
                        {subtitle}
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/95 p-6 text-center text-slate-400">
                  <div className="w-14 h-14 rounded-full bg-slate-800 flex items-center justify-center mb-3">
                    <User className="w-7 h-7 text-slate-500" />
                  </div>
                  <p className="text-sm font-medium text-slate-300">对方视频未连接</p>
                  <p className="text-xs text-slate-500 max-w-xs mt-1 leading-relaxed">
                    您可以主动邀请高级手语翻译梅（Mei）开启双向通话。
                  </p>
                  <button
                    onClick={triggerIncomingCall}
                    className="mt-4 px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors flex items-center gap-1.5 shadow-md"
                  >
                    <BellRing className="w-3.5 h-3.5" /> 模拟外线来电
                  </button>
                </div>
              )}

              <div className="absolute top-3 left-3 z-10 flex gap-2">
                <span className="bg-indigo-600/90 text-white text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1 shadow-md">
                  <span className={`w-1.5 h-1.5 rounded-full ${callState === "connected" ? "bg-emerald-400 animate-ping" : "bg-slate-400"}`} />
                  远程席位 (PEER)
                </span>
              </div>
            </div>
          </div>

        </div>

        {/* Hand Sign Interactive Sender Dashboard */}
        <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 shadow-lg">
          <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
            <h4 className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-teal-400" />
              听障专用无触输入：一键手势力学模拟
            </h4>
            <span className="text-[10px] text-slate-400 bg-slate-900 px-2 py-1 rounded-full border border-slate-800">
              点按选项将在本地摄像头画出骨骼，并经 AI 转换为文字发送至信道
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
            {SIGN_DATABASE.map((item) => (
              <button
                key={item.id}
                onClick={() => handlePerformLocalGesture(item.id)}
                className="flex items-center gap-1.5 p-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 hover:bg-slate-800 text-left transition-all duration-200 group text-xs text-slate-100"
              >
                <span className="text-lg group-hover:scale-125 transition-transform">{item.emoji}</span>
                <div className="overflow-hidden">
                  <p className="font-bold text-slate-200 line-clamp-1">{item.word}</p>
                  <p className="text-[10px] text-slate-400 truncate">{item.translation}</p>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* RTC Network & HD Stream Statistics Widget */}
        <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 shadow-md">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-4 h-4 text-teal-400" />
            <h4 className="text-xs font-mono font-bold text-slate-200 uppercase tracking-wider">
              WebRTC SFU 低延迟高清链路指标流 (实时采集)
            </h4>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
            <div className="flex flex-col">
              <span className="text-[10px] text-slate-500 font-mono">延迟速率</span>
              <span className="text-base font-mono font-bold text-emerald-400 flex items-center gap-1">
                <Zap className="w-3.5 h-3.5 text-emerald-500" />
                {callState === "connected" ? `${metrics.latencyMs} ms` : "--"}
              </span>
            </div>
            <div className="flex flex-col">
              <span className="text-[10px] text-slate-500 font-mono">帧率</span>
              <span className="text-base font-mono font-bold text-slate-200">
                {callState === "connected" ? `${metrics.fps} FPS` : "--"}
              </span>
            </div>
            <div className="flex flex-col">
              <span className="text-[10px] text-slate-500 font-mono">视频分辨率</span>
              <span className="text-base font-mono font-bold text-slate-200">
                {callState === "connected" ? metrics.resolution : "--"}
              </span>
            </div>
            <div className="flex flex-col">
              <span className="text-[10px] text-slate-500 font-mono">传输信道带宽</span>
              <span className="text-base font-mono font-bold text-slate-200">
                {callState === "connected" ? `${metrics.bitrateKbps} Kbps` : "--"}
              </span>
            </div>
            <div className="flex flex-col">
              <span className="text-[10px] text-slate-500 font-mono">数据包丢失</span>
              <span className="text-base font-mono font-bold text-emerald-400">
                {callState === "connected" ? `${metrics.packetLoss}%` : "--"}
              </span>
            </div>
            <div className="flex flex-col">
              <span className="text-[10px] text-slate-500 font-mono">加密协议</span>
              <span className="text-[11px] font-mono font-bold text-indigo-400">
                {callState === "connected" ? "SRTP-AES256" : "--"}
              </span>
            </div>
          </div>
        </div>

      </div>

      {/* RIGHT: Low-Latency Secure Text Channel (4 columns) */}
      <div className="lg:col-span-4 flex flex-col h-[520px] md:h-[620px] bg-slate-950 rounded-2xl border border-slate-800 shadow-xl overflow-hidden">
        
        {/* Chat Title Headers */}
        <div className="p-4 border-b border-slate-800 bg-slate-900 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-200 flex items-center gap-1.5">
              <MessageSquare className="w-4 h-4 text-indigo-400" />
              文本与手语中转信道
            </h3>
            <p className="text-[10px] text-slate-400">已开启端到端双向加密 (SRTP)</p>
          </div>

          <div className="flex gap-1">
            {callState === "connected" ? (
              <button
                onClick={handleDeclineCall}
                className="p-2 bg-rose-950 text-rose-300 hover:bg-rose-900 rounded-lg text-xs transition-all flex items-center gap-1"
                title="挂断通话"
              >
                <PhoneOff className="w-3.5 h-3.5" />挂断
              </button>
            ) : (
                <button
                  onClick={handleAcceptCall}
                  className="p-2 bg-emerald-950 text-emerald-300 hover:bg-emerald-900 rounded-lg text-xs transition-all flex items-center gap-1 font-bold"
                >
                  <Phone className="w-3.5 h-3.5" />拨通
                </button>
            )}
          </div>
        </div>

        {/* Messaging Box Panel */}
        <div className="flex-1 p-4 overflow-y-auto space-y-3 flex flex-col justify-end" id="message_scroller">
          <div className="space-y-3 max-h-[360px] md:max-h-[440px] overflow-y-auto pr-1">
            {messages.map((m) => {
              const isSelf = m.sender === "self";
              const isSystem = m.sender === "system";

              if (isSystem) {
                return (
                  <div key={m.id} className="text-center">
                    <span className="inline-block px-3 py-1 bg-slate-900 rounded-lg text-[10px] text-slate-400 max-w-sm border border-slate-800 leading-relaxed font-mono">
                      {m.text}
                    </span>
                  </div>
                );
              }

              return (
                <div key={m.id} className={`flex flex-col ${isSelf ? "items-end" : "items-start"}`}>
                  <div
                    className={`max-w-[85%] rounded-2xl p-3 text-xs leading-relaxed shadow-md ${
                      isSelf
                        ? m.isGesture
                          ? "bg-teal-900/40 text-teal-100 rounded-tr-none border border-teal-500/30"
                          : "bg-slate-800 text-slate-100 rounded-tr-none border border-slate-700"
                        : m.isGesture
                        ? "bg-indigo-950/40 text-indigo-100 rounded-tl-none border border-indigo-500/30 text-left"
                        : "bg-slate-900 text-slate-200 rounded-tl-none border border-slate-850"
                    }`}
                  >
                    {m.isGesture && (
                      <div className="flex items-center gap-1 mb-1 text-[9px] font-mono tracking-wider font-bold text-teal-400">
                        <Sparkles className="w-2.5 h-2.5 animate-pulse" />
                        <span>AI GESTURE REALTIME</span>
                      </div>
                    )}
                    <p className={fontSizeClass}>{m.text}</p>
                  </div>
                  <span className="text-[9px] text-slate-500 font-mono mt-1 px-1">
                    {isSelf ? "您" : "梅"} · {m.timestamp}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Input box field form */}
        <form onSubmit={handleSendMessage} className="p-3 border-t border-slate-800 bg-slate-900/50 flex gap-2">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="打字输入发送 (听障同声传译已开启)..."
            className="flex-1 bg-slate-950 border border-slate-850 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
          />
          <button
            type="submit"
            className="p-2 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-white transition-colors flex items-center justify-center shadow-lg"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>

      </div>

    </div>
  );
}
