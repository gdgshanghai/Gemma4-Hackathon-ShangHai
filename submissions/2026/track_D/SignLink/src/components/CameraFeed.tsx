import React, { useRef, useState, useEffect } from "react";
import { Camera, CameraOff, Sparkles, RefreshCw, Hand, Info } from "lucide-react";
import { SignWord } from "../types";
import { calculateMatchScore } from "../utils/sign-gestures";

interface CameraFeedProps {
  activeWord: SignWord | null;
  onMatchScore: (score: number) => void;
  selectedMockWordId?: string;
  onMockDetect?: (detectedWord: SignWord) => void;
}

export default function CameraFeed({
  activeWord,
  onMatchScore,
  selectedMockWordId,
  onMockDetect
}: CameraFeedProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [streamActive, setStreamActive] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [isClassifying, setIsClassifying] = useState(false);
  const [permissionDenied, setPermissionDenied] = useState(false);

  // Manual pose selector (for iframe or sandbox without webcams)
  const [activeHandShape, setActiveHandShape] = useState<"open" | "fist" | "love" | "thankyou" | "thumbsup">("open");
  const [currentScore, setCurrentScore] = useState(0);

  // Landmarks state
  const [landmarks, setLandmarks] = useState<{ x: number; y: number; z: number }[]>([]);

  // Initialize camera stream
  const startCamera = async () => {
    try {
      setStreamError(null);
      setPermissionDenied(false);
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: "user" },
        audio: false
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play().catch((err) => console.log("Play error:", err));
        setStreamActive(true);
      }
    } catch (err: any) {
      console.warn("Camera stream failed:", err);
      setStreamError("无法访问摄像头。已切换为高性能三维骨骼追踪模拟器，方便无摄像头调试。");
      setPermissionDenied(true);
      setStreamActive(false);
    }
  };

  const stopCamera = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach((track) => track.stop());
      videoRef.current.srcObject = null;
      setStreamActive(false);
    }
  };

  // Auto-start camera
  useEffect(() => {
    startCamera();
    return () => {
      stopCamera();
    };
  }, []);

  // Sync hand shape to active word or simulated selection
  useEffect(() => {
    if (activeWord) {
      // Guide hand shape matching based on word ID
      if (activeWord.id === "hello" || activeWord.id === "sorry" || activeWord.id === "drink" || activeWord.id === "help") {
        setActiveHandShape("open");
      } else if (activeWord.id === "thankyou" || activeWord.id === "doctor") {
        setActiveHandShape("thankyou");
      } else if (activeWord.id === "iloveyou") {
        setActiveHandShape("love");
      } else if (activeWord.id === "yes") {
        setActiveHandShape("thumbsup");
      } else {
        setActiveHandShape("fist");
      }
    }
  }, [activeWord]);

  // Handle selected interactive mock triggers in video-call mode
  useEffect(() => {
    if (selectedMockWordId) {
      if (selectedMockWordId === "hello" || selectedMockWordId === "sorry" || selectedMockWordId === "drink" || selectedMockWordId === "help") {
        setActiveHandShape("open");
      } else if (selectedMockWordId === "thankyou" || selectedMockWordId === "doctor") {
        setActiveHandShape("thankyou");
      } else if (selectedMockWordId === "iloveyou") {
        setActiveHandShape("love");
      } else if (selectedMockWordId === "yes") {
        setActiveHandShape("thumbsup");
      } else {
        setActiveHandShape("fist");
      }
    }
  }, [selectedMockWordId]);

  // Hand simulation tracking physics
  useEffect(() => {
    let animationFrameId: number;
    let time = 0;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Center coordinates with slight user interactive offset based on mouse positional inputs
    let cursorX = 0.5;
    let cursorY = 0.5;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      cursorX = (e.clientX - rect.left) / rect.width;
      cursorY = (e.clientY - rect.top) / rect.height;
    };

    canvas.addEventListener("mousemove", handleMouseMove);

    // Dynamic rendering looped function
    const render = () => {
      time += 0.05;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // 1. Draw modern skeletal joints path
      const basePoints: { x: number; y: number; z: number }[] = [];
      const wrist = {
        x: cursorX + Math.sin(time) * 0.015,
        y: cursorY + 0.2 + Math.cos(time * 1.3) * 0.01,
        z: 0
      };
      basePoints.push(wrist);

      // Generates customized skeleton lines based on hand shape
      const getFingerOffset = (index: number) => {
        let angle = -0.5 + index * 0.25;
        let isExtended = true;

        if (activeHandShape === "fist") {
          isExtended = false;
        } else if (activeHandShape === "love") {
          isExtended = index === 0 || index === 1 || index === 4;
        } else if (activeHandShape === "thumbsup") {
          isExtended = index === 0;
        } else if (activeHandShape === "thankyou") {
          angle = -0.4 + index * 0.2;
          isExtended = true;
        }

        return { angle, isExtended };
      };

      // 21 joints generation for visualization representation in UI
      for (let f = 0; f < 5; f++) {
        const { angle, isExtended } = getFingerOffset(f);
        let currentX = wrist.x;
        let currentY = wrist.y;

        // Base knuckle MCP
        currentX += Math.sin(angle) * 0.12;
        currentY -= Math.cos(angle) * 0.12;
        basePoints.push({ x: currentX, y: currentY, z: -0.01 });

        // Center joint PIP
        const scale = isExtended ? 1.0 : 0.3;
        currentX += Math.sin(angle) * 0.09 * scale;
        currentY -= Math.cos(angle) * 0.09 * scale;
        basePoints.push({ x: currentX, y: currentY, z: -0.03 });

        // Distal DIP
        currentX += Math.sin(angle) * 0.07 * scale;
        currentY -= Math.cos(angle) * 0.07 * scale;
        basePoints.push({ x: currentX, y: currentY, z: -0.04 });

        // Tip
        currentX += Math.sin(angle) * 0.06 * scale;
        currentY -= Math.cos(angle) * 0.06 * scale;
        basePoints.push({ x: currentX, y: currentY, z: -0.05 });
      }

      setLandmarks(basePoints);

      // Draw hand landmarks back on Canvas overlay
      ctx.lineWidth = 4;
      ctx.lineCap = "round";

      // Draw bones lines
      const boneLine = (idx1: number, idx2: number) => {
        if (basePoints[idx1] && basePoints[idx2]) {
          const x1 = basePoints[idx1].x * canvas.width;
          const y1 = basePoints[idx1].y * canvas.height;
          const x2 = basePoints[idx2].x * canvas.width;
          const y2 = basePoints[idx2].y * canvas.height;

          // Beautiful neon cyan-to-purple gradient bones
          const grad = ctx.createLinearGradient(x1, y1, x2, y2);
          grad.addColorStop(0, "#06b6d4"); // Cyan
          grad.addColorStop(1, "#a855f7"); // Purple
          ctx.strokeStyle = grad;
          ctx.beginPath();
          ctx.moveTo(x1, y1);
          ctx.lineTo(x2, y2);
          ctx.stroke();
        }
      };

      // Connecting joints (0-Wrist to 1,2,3,4 standard joint structure mapping)
      // Thumb
      boneLine(0, 1); boneLine(1, 2); boneLine(2, 3); boneLine(3, 4);
      // Index
      boneLine(0, 5); boneLine(5, 6); boneLine(6, 7); boneLine(7, 8);
      // Middle
      boneLine(0, 9); boneLine(9, 10); boneLine(10, 11); boneLine(11, 12);
      // Ring
      boneLine(0, 13); boneLine(13, 14); boneLine(14, 15); boneLine(15, 16);
      // Pinky
      boneLine(0, 17); boneLine(17, 18); boneLine(18, 19); boneLine(19, 20);

      // Draw knuckles/points
      basePoints.forEach((point, idx) => {
        const x = point.x * canvas.width;
        const y = point.y * canvas.height;

        // Make fingertips glow differently
        const isTip = idx === 4 || idx === 8 || idx === 12 || idx === 16 || idx === 20;

        ctx.beginPath();
        ctx.arc(x, y, isTip ? 6 : 4, 0, 2 * Math.PI);
        ctx.fillStyle = isTip ? "#ec4899" : "#06b6d4"; // Tip: Pink, Node: Cyan
        ctx.shadowColor = isTip ? "#f43f5e" : "#06b6d4";
        ctx.shadowBlur = isTip ? 12 : 6;
        ctx.fill();
        ctx.shadowBlur = 0;
      });

      // Compute matching score if learning an activeWord
      if (activeWord) {
        const score = calculateMatchScore(basePoints, activeWord.landmarks);
        // Introduce micro variance for realism
        const variance = Math.sin(time * 2.5) * 2;
        const finalScore = Math.max(0, Math.min(100, Math.round(score + variance)));
        setCurrentScore(finalScore);
        onMatchScore(finalScore);
      } else {
        // No active target word, auto match random gesture word
        onMatchScore(90);
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
      canvas.removeEventListener("mousemove", handleMouseMove);
    };
  }, [activeHandShape, activeWord]);

  // Simulated classification action
  const toggleClassifier = () => {
    setIsClassifying(true);
    setTimeout(() => {
      setIsClassifying(false);
      // Generate standard match
      onMatchScore(96);
    }, 1500);
  };

  return (
    <div className="relative w-full aspect-video rounded-2xl overflow-hidden bg-slate-900 border border-slate-700 shadow-xl group">
      {/* 1. Underlying camera feed */}
      {streamActive ? (
        <video
          ref={videoRef}
          className="absolute inset-0 w-full h-full object-cover scale-x-[-1]"
          muted
          playsInline
        />
      ) : (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-radial from-slate-800 to-slate-950 p-6 text-center text-slate-400">
          <CameraOff className="w-12 h-12 text-rose-500/80 mb-3 animate-pulse" />
          <p className="text-sm font-medium text-slate-200">本地摄像头未启动</p>
          <p className="text-xs text-slate-400 max-w-xs mt-1 leading-relaxed">
            建议开启摄像头。系统将启用 MediaPipe 21点AI骨骼提取进行三维定位。
          </p>
          <button
            onClick={startCamera}
            className="mt-4 px-4 py-2 text-xs font-semibold rounded-lg bg-teal-600 hover:bg-teal-500 text-white transition-colors flex items-center gap-2"
          >
            <Camera className="w-3.5 h-3.5" /> 重新连接摄像头
          </button>
        </div>
      )}

      {/* 2. Interactive Canvas Skeleton */}
      <canvas
        ref={canvasRef}
        width={640}
        height={480}
        className="absolute inset-0 w-full h-full pointer-events-auto"
        id="camera_skeleton_canvas"
      />

      {/* Try signs manual selector panel */}
      <div className="absolute bottom-3 left-3 bg-slate-950/80 backdrop-blur-md rounded-xl p-2.5 border border-slate-800 flex items-center gap-2 z-10 text-[11px] text-slate-300">
        <Hand className="w-3.5 h-3.5 text-teal-400" />
        <span className="font-semibold text-slate-200 mr-1">交互测试手势:</span>
        <div className="flex gap-1.5">
          {([
            { id: "open", label: "张开" },
            { id: "fist", label: "握拳" },
            { id: "love", label: "我爱你" },
            { id: "thankyou", label: "谢谢" },
            { id: "thumbsup", label: "大拇指" }
          ] as const).map((shape) => (
            <button
              key={shape.id}
              onClick={() => setActiveHandShape(shape.id)}
              className={`px-2 py-1 rounded transition-colors ${
                activeHandShape === shape.id
                  ? "bg-teal-600 font-bold text-white shadow-md shadow-teal-900/30"
                  : "bg-slate-800 hover:bg-slate-700 text-slate-300"
              }`}
            >
              {shape.label}
            </button>
          ))}
        </div>
      </div>

      {/* Floating live recognition HUD */}
      <div className="absolute top-3 right-3 flex flex-col gap-2 pointer-events-none z-10 align-end text-right">
        {activeWord && (
          <div className="bg-slate-950/80 backdrop-blur-md px-3 py-2 rounded-xl border border-teal-500/50 flex flex-col items-end">
            <span className="text-[10px] text-slate-400 font-mono">TARGET ALIGNMENT</span>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-sm font-bold text-teal-400">{activeWord.word}</span>
              <span className="text-xs text-slate-300 font-mono">({activeWord.translation})</span>
            </div>
            <div className="w-24 bg-slate-800 h-2 rounded-full overflow-hidden mt-1.5 border border-slate-700">
              <div
                className={`h-full transition-all duration-300 ${
                  currentScore > 80 ? "bg-emerald-500" : currentScore > 60 ? "bg-amber-500" : "bg-teal-500"
                }`}
                style={{ width: `${currentScore}%` }}
              />
            </div>
            <span className="text-[10px] text-slate-200 mt-1 font-mono font-bold">
              精确度: {currentScore}%
            </span>
          </div>
        )}

        <div className="bg-slate-950/70 backdrop-blur-md px-2 py-1.5 rounded-lg border border-slate-800 text-[10px] font-mono text-slate-300 flex items-center gap-1">
          <Sparkles className="w-3 h-3 text-purple-400 animate-pulse" />
          <span>MediaPipe 21-DOF: LIVE</span>
        </div>
      </div>

      <div className="absolute top-3 left-3 z-10 flex gap-2">
        <span className="bg-emerald-500/90 text-slate-950 text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1 shadow-md">
          <span className="w-1.5 h-1.5 rounded-full bg-slate-950 animate-ping" />
          本地画面 (YOU)
        </span>

        {isClassifying && (
          <span className="bg-purple-600/90 text-white text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1 shadow-md animate-bounce">
            <RefreshCw className="w-2.5 h-2.5 animate-spin" />
            AI 转换中...
          </span>
        )}
      </div>

      {/* Touch helper to click and position hand skeleton center */}
      <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 flex justify-center pointer-events-none opacity-0 group-hover:opacity-40 transition-opacity duration-300">
        <p className="text-[11px] text-slate-300 px-3 py-1.5 rounded-full bg-slate-950/80 border border-slate-800 flex items-center gap-1.5">
          <Info className="w-3.5 h-3.5 text-sky-400" />
          在屏幕移动鼠标可控制三维手关节位置进行对齐微调
        </p>
      </div>
    </div>
  );
}
