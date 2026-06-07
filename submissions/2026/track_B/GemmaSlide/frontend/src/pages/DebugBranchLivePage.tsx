import { useCallback, useEffect, useRef, useState } from "react";

import { fetchPrecomputedBranches, parsePptxOnly } from "../api";
import { AppTopBar } from "../components/AppTopBar";
import { DebugToolTabs } from "../components/DebugToolTabs";
import { useLiveSession } from "../lib/use-live-session";
import type {
  BranchActionType,
  BranchMatchResult,
  BranchNode,
  ParsePptxResponse,
  PrecomputedBranchesResponse,
} from "../types";

// ── Constants ──

const ACTION_COLORS: Record<
  BranchActionType,
  { bg: string; text: string; border: string; icon: string }
> = {
  highlight: {
    bg: "bg-yellow-50",
    text: "text-yellow-800",
    border: "border-yellow-300",
    icon: "🖍️",
  },
  circle: {
    bg: "bg-blue-50",
    text: "text-blue-800",
    border: "border-blue-300",
    icon: "⭕",
  },
  arrow: {
    bg: "bg-green-50",
    text: "text-green-800",
    border: "border-green-300",
    icon: "➡️",
  },
  transition: {
    bg: "bg-purple-50",
    text: "text-purple-800",
    border: "border-purple-300",
    icon: "📄",
  },
  none: {
    bg: "bg-gray-50",
    text: "text-gray-600",
    border: "border-gray-200",
    icon: "💬",
  },
};

const OVERLAY_COLORS: Record<BranchActionType, string> = {
  highlight: "rgba(234,179,8,0.35)",
  circle: "rgba(59,130,246,0.35)",
  arrow: "rgba(34,197,94,0.35)",
  transition: "transparent",
  none: "transparent",
};

const OVERLAY_BORDER: Record<BranchActionType, string> = {
  highlight: "#ca8a04",
  circle: "#2563eb",
  arrow: "#16a34a",
  transition: "transparent",
  none: "transparent",
};

// ── Helpers ──

function flattenBboxes(branches: BranchNode[]) {
  const res: {
    branch_id: string;
    bbox_1000: number[];
    action_type: BranchActionType;
  }[] = [];
  const walk = (nodes: BranchNode[]) => {
    for (const n of nodes) {
      if (
        n.action.type !== "none" &&
        n.action.type !== "transition" &&
        n.action.bbox_1000.length === 4
      ) {
        res.push({
          branch_id: n.branch_id,
          bbox_1000: n.action.bbox_1000,
          action_type: n.action.type,
        });
      }
      walk(n.next_branches);
    }
  };
  walk(branches);
  return res;
}

// ── Branch Card ──

function BranchCard({
  node,
  selectedId,
  coveredIds,
}: {
  node: BranchNode;
  selectedId: string | null;
  coveredIds: string[];
}) {
  const c = ACTION_COLORS[node.action.type] ?? ACTION_COLORS.none;
  const isSel = selectedId === node.branch_id;
  const isCovered = coveredIds.includes(node.branch_id);
  return (
    <div className="mb-2">
      <div
        className={`w-full text-left rounded-xl border ${c.border} ${isCovered ? "bg-gray-100 opacity-70" : c.bg} p-3 transition-all ${isSel ? "ring-2 ring-offset-1 ring-blue-500" : ""}`}
      >
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-mono font-semibold text-gray-500">
            {node.branch_id}
          </span>
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${c.text}`}
          >
            {c.icon} {node.action.type}
          </span>
          {isCovered && (
            <span className="text-xs text-green-600 font-semibold">
              ✓ Covered
            </span>
          )}
        </div>
        <p
          className={`text-sm font-medium ${isCovered ? "text-gray-400 line-through" : "text-gray-800"}`}
        >
          {node.predicted_text}
        </p>
        {node.teleprompter && node.teleprompter !== node.predicted_text && (
          <p className="text-xs text-gray-500 italic mt-0.5">
            📋 {node.teleprompter}
          </p>
        )}
      </div>
      {node.next_branches.length > 0 && (
        <div className="ml-4 border-l-2 border-gray-200 pl-3 mt-1">
          {node.next_branches.map((c) => (
            <BranchCard
              key={c.branch_id}
              node={c}
              selectedId={selectedId}
              coveredIds={coveredIds}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Slide Preview ──

function SlidePreview({
  imageBase64,
  widthPx,
  heightPx,
  bboxes,
  selectedId,
  coveredIds,
}: {
  imageBase64: string;
  widthPx: number;
  heightPx: number;
  bboxes: ReturnType<typeof flattenBboxes>;
  selectedId: string | null;
  coveredIds: string[];
}) {
  return (
    <div
      className="relative mx-auto border border-gray-200 rounded-lg overflow-hidden bg-white shadow-sm"
      style={{ maxWidth: 600, aspectRatio: `${widthPx}/${heightPx}` }}
    >
      <img
        src={imageBase64}
        alt="slide"
        className="w-full h-full object-contain"
      />
      {bboxes.map((bb) => {
        const [ymin, xmin, ymax, xmax] = bb.bbox_1000;
        const isSel = selectedId === bb.branch_id;
        const isCovered = coveredIds.includes(bb.branch_id);
        return (
          <div
            key={bb.branch_id}
            className={`absolute pointer-events-none transition-all duration-200 ${isSel ? "z-10 ring-2 ring-blue-500 opacity-90" : isCovered ? "opacity-20" : "opacity-60"}`}
            style={{
              top: `${(ymin / 1000) * 100}%`,
              left: `${(xmin / 1000) * 100}%`,
              height: `${((ymax - ymin) / 1000) * 100}%`,
              width: `${((xmax - xmin) / 1000) * 100}%`,
              background: OVERLAY_COLORS[bb.action_type],
              border: `2px solid ${isCovered ? "#22c55e" : OVERLAY_BORDER[bb.action_type]}`,
            }}
          >
            {isCovered && (
              <span className="absolute top-0 right-0 text-[10px] text-green-600 font-bold">
                ✓
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Main Page ──

export default function DebugBranchLivePage() {
  // Upload state
  const [file, setFile] = useState<File | null>(null);
  const [parseResult, setParseResult] = useState<ParsePptxResponse | null>(
    null,
  );
  const [parseId, setParseId] = useState("");
  const [branchesData, setBranchesData] =
    useState<PrecomputedBranchesResponse | null>(null);
  const [selectedSlide, setSelectedSlide] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Live ASR + branch match
  const live = useLiveSession();
  const {
    status: liveStatus,
    asrText,
    matchResult,
    trackResult,
    currentSlideIndex,
    start: startLive,
    stop: stopLive,
  } = live;

  // Accumulate covered branch IDs from tracker
  const [coveredIds, setCoveredIds] = useState<string[]>([]);
  useEffect(() => {
    if (trackResult?.all_covered_ids) {
      setCoveredIds(trackResult.all_covered_ids);
    }
  }, [trackResult]);

  // Auto-follow backend-driven slide transitions (branch-match transition)
  useEffect(() => {
    if (currentSlideIndex > 0) {
      setSelectedSlide(currentSlideIndex);
      setCoveredIds([]); // reset covered on slide change
    }
  }, [currentSlideIndex]);

  // Match history
  const [matchHistory, setMatchHistory] = useState<BranchMatchResult[]>([]);
  const prevMatchRef = useRef<string | null>(null);

  useEffect(() => {
    if (matchResult && matchResult.branch_id !== prevMatchRef.current) {
      prevMatchRef.current = matchResult.branch_id;
      setMatchHistory((h) => [matchResult, ...h].slice(0, 30));
    }
  }, [matchResult]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleUpload = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!file) return;
      setLoading(true);
      setError("");
      stopLive();
      setMatchHistory([]);
      try {
        const res = await parsePptxOnly(file, {
          includeImagesBase64: true,
          flattenGroups: true,
          elementTypes: [],
        });
        setParseResult(res);
        setParseId(res.parse_id);
        setSelectedSlide(0);
        setBranchesData(null);
        pollRef.current = setInterval(async () => {
          try {
            const bd = await fetchPrecomputedBranches(res.parse_id);
            setBranchesData(bd);
            if (bd.ready && pollRef.current) {
              clearInterval(pollRef.current);
              pollRef.current = null;
            }
          } catch {
            /* ignore */
          }
        }, 2000);
      } catch (err) {
        setError(String(err));
      } finally {
        setLoading(false);
      }
    },
    [file, stopLive],
  );

  const isRecording = liveStatus === "recording";
  const handleToggleRecord = useCallback(() => {
    if (isRecording) {
      stopLive();
    } else if (parseId) {
      setMatchHistory([]);
      prevMatchRef.current = null;
      setCoveredIds([]);
      startLive(parseId);
    }
  }, [isRecording, parseId, startLive, stopLive]);

  const slideCount = parseResult?.total_slides ?? 0;
  const currentBranches = branchesData?.branches[selectedSlide] ?? [];
  const readyCount = branchesData
    ? Object.keys(branchesData.branches).length
    : 0;
  const currentSlide = parseResult?.slides[selectedSlide];
  const bboxes = flattenBboxes(currentBranches);
  const matchedId = matchResult?.branch_id ?? null;

  return (
    <div className="min-h-screen bg-gray-50">
      <AppTopBar
        title="Debug Branch Live"
        subtitle="Real-time ASR + Branch Matching"
      />
      <DebugToolTabs />
      <div className="max-w-7xl mx-auto px-4 pb-8 space-y-4">
        {/* Upload + Record bar */}
        <div className={`rounded-2xl border bg-card p-4`}>
          <form
            onSubmit={handleUpload}
            className="flex items-center gap-3 flex-wrap"
          >
            <input
              type="file"
              accept=".pptx"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!file || loading}
              className="px-5 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-40 font-medium text-sm"
            >
              {loading ? "Uploading..." : "Upload & Precompute"}
            </button>
            {parseId && (
              <span className="text-xs text-gray-500 font-mono">
                {readyCount}/{slideCount} ready
                {branchesData?.ready ? " ✅" : " ⏳"}
              </span>
            )}
            {branchesData?.ready && (
              <button
                type="button"
                onClick={handleToggleRecord}
                className={`px-5 py-2 rounded-xl font-medium text-sm text-white transition-all ${
                  isRecording
                    ? "bg-red-600 hover:bg-red-700 animate-pulse"
                    : "bg-green-600 hover:bg-green-700"
                }`}
              >
                {isRecording ? "⏹ Stop" : "🎤 Start Mic"}
              </button>
            )}
          </form>
          {error && <p className="text-red-600 text-sm mt-2">{error}</p>}
        </div>

        {parseResult && (
          <>
            {/* Slide tabs */}
            <div className="flex gap-2 flex-wrap">
              {parseResult.slides.map((_s, i) => {
                const hasBranches =
                  (branchesData?.branches[i]?.length ?? 0) > 0;
                return (
                  <button
                    key={i}
                    onClick={() => setSelectedSlide(i)}
                    className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                      selectedSlide === i
                        ? "bg-blue-600 text-white shadow"
                        : hasBranches
                          ? "bg-green-100 text-green-800 hover:bg-green-200"
                          : "bg-gray-100 text-gray-500"
                    }`}
                  >
                    #{i + 1}
                    {hasBranches ? " ✓" : ""}
                  </button>
                );
              })}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Left: Slide + ASR + Branches */}
              <div className="lg:col-span-2 space-y-4">
                {/* Slide preview */}
                <div className={`rounded-2xl border bg-card p-4`}>
                  <h3 className="text-sm font-semibold text-gray-500 mb-2">
                    Slide {selectedSlide + 1}
                    {isRecording && (
                      <span className="ml-2 text-red-500 animate-pulse text-xs">
                        🔴 LIVE
                      </span>
                    )}
                  </h3>
                  {currentSlide?.image?.image_base64 && (
                    <SlidePreview
                      imageBase64={currentSlide.image.image_base64}
                      widthPx={currentSlide.image.width_px}
                      heightPx={currentSlide.image.height_px}
                      bboxes={bboxes}
                      selectedId={matchedId}
                      coveredIds={coveredIds}
                    />
                  )}
                  {/* Real-time ASR text */}
                  {isRecording && asrText && (
                    <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-xl">
                      <p className="text-xs text-blue-500 font-semibold mb-1">
                        🎙️ ASR
                      </p>
                      <p className="text-sm text-blue-900">{asrText}</p>
                    </div>
                  )}
                </div>

                {/* Live match card */}
                {matchResult && (
                  <div
                    className={`rounded-2xl border bg-card p-4 border-2 ${ACTION_COLORS[matchResult.action.type]?.border ?? "border-gray-200"}`}
                  >
                    <h3 className="text-sm font-semibold text-gray-500 mb-2">
                      🎯 Live Match
                      {matchResult.is_covered && (
                        <span className="ml-2 text-xs text-green-600 font-bold">
                          ✓ COVERED
                        </span>
                      )}
                      {trackResult && trackResult.segment_count > 1 && (
                        <span className="ml-2 text-xs text-gray-400">
                          · {trackResult.segment_count} segments
                        </span>
                      )}
                    </h3>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-mono text-gray-500">
                        {matchResult.branch_id}
                      </span>
                      <span
                        className={`text-xs font-semibold px-2 py-0.5 rounded-full ${ACTION_COLORS[matchResult.action.type]?.text ?? "text-gray-600"}`}
                      >
                        {ACTION_COLORS[matchResult.action.type]?.icon}{" "}
                        {matchResult.action.type}
                      </span>
                      <span className="text-xs text-gray-400">
                        {(matchResult.confidence * 100).toFixed(1)}% ·{" "}
                        {matchResult.elapsed_ms.toFixed(0)}ms
                      </span>
                    </div>
                    <p className="text-sm font-medium">
                      {matchResult.predicted_text}
                    </p>
                    {matchResult.teleprompter && (
                      <p className="text-xs text-gray-500 mt-1">
                        📋 {matchResult.teleprompter}
                      </p>
                    )}
                    {trackResult && trackResult.covered_ids.length > 0 && (
                      <p className="text-xs text-green-600 mt-1">
                        ✓ Just covered: {trackResult.covered_ids.join(", ")}
                      </p>
                    )}
                  </div>
                )}

                {/* Branch tree */}
                <div className={`rounded-2xl border bg-card p-4`}>
                  <h3 className="text-sm font-semibold text-gray-500 mb-2">
                    Branches ({currentBranches.length})
                  </h3>
                  {currentBranches.map((n) => (
                    <BranchCard
                      key={n.branch_id}
                      node={n}
                      selectedId={matchedId}
                      coveredIds={coveredIds}
                    />
                  ))}
                  {currentBranches.length === 0 && (
                    <p className="text-gray-400 text-sm">
                      Waiting for branches...
                    </p>
                  )}
                </div>
              </div>

              {/* Right: Match History */}
              <div className={`rounded-2xl border bg-card p-4`}>
                <h3 className="text-sm font-semibold text-gray-500 mb-3">
                  Match History ({matchHistory.length})
                </h3>
                {matchHistory.length === 0 && (
                  <p className="text-gray-400 text-sm">
                    Start recording to see matches...
                  </p>
                )}
                <div className="space-y-2 max-h-[600px] overflow-y-auto">
                  {matchHistory.map((m, i) => {
                    const c =
                      ACTION_COLORS[m.action.type] ?? ACTION_COLORS.none;
                    return (
                      <div
                        key={`${m.branch_id}-${i}`}
                        className={`rounded-lg border ${c.border} p-2 text-xs`}
                      >
                        <div className="flex items-center gap-1.5 mb-0.5">
                          <span className="font-mono text-gray-500">
                            {m.branch_id}
                          </span>
                          <span className={`font-semibold ${c.text}`}>
                            {c.icon} {m.action.type}
                          </span>
                          <span className="text-gray-400">
                            {(m.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                        <p className="text-gray-700 line-clamp-2">
                          {m.predicted_text}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
