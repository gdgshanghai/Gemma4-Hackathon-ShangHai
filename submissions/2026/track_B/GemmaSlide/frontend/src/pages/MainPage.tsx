import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  fetchPrecomputedBranches,
  parsePptxOnly,
  streamBranchEvents,
  submitPptxScriptJob,
} from "../api";
import { AppTopBar } from "../components/AppTopBar";
import { LiveBranchList } from "../components/LiveBranchList";
import { ScriptPlaybackPanel } from "../components/ScriptPlaybackPanel";
import { useJobSse } from "../lib/use-job-sse";
import { useLiveSession } from "../lib/use-live-session";
import {
  buildPlaybackTimeline,
  useScriptPlayback,
  type PlaybackTimelineItem,
} from "../lib/use-script-playback";
import type {
  BranchActionType,
  BranchNode,
  PrecomputedBranchesResponse,
  PptxScriptJobStatus,
  PptxScriptSseEvent,
  SlideReadySseEvent,
  SlideScript,
} from "../types";

type PresentationMode = "auto" | "live";

type AppState =
  | "idle"
  | "uploading"
  | "job-pending"
  | "streaming"
  | "sliding"
  | "ready-to-play"
  | "playing"
  | "paused"
  | "live-ready"
  | "precomputing";

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

export function MainPage() {
  const [file, setFile] = useState<File | null>(null);
  const [appState, setAppState] = useState<AppState>("idle");
  const [mode, setMode] = useState<PresentationMode>("auto");
  const [jobId, setJobId] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [latestStatus, setLatestStatus] = useState<PptxScriptJobStatus | null>(
    null,
  );
  const [allSlides, setAllSlides] = useState<SlideScript[]>([]);
  const [parseId, setParseId] = useState<string>("");
  const [totalSlides, setTotalSlides] = useState(0);
  const [timeline, setTimeline] = useState<PlaybackTimelineItem[]>([]);
  const [scriptResultFile, setScriptResultFile] = useState<string | null>(null);
  const [branchesData, setBranchesData] =
    useState<PrecomputedBranchesResponse | null>(null);
  const branchAbortRef = useRef<AbortController | null>(null);
  const [liveSlideIndex, setLiveSlideIndex] = useState(0);

  // Refs to accumulate slides from SSE without closure issues
  const slidesRef = useRef<SlideScript[]>([]);
  const slideIndicesRef = useRef<Set<number>>(new Set());

  const playback = useScriptPlayback(timeline);
  const live = useLiveSession();
  const activeSlide = playback.activeSegment?.slide ?? null;

  const canSubmit =
    appState === "idle" ||
    appState === "ready-to-play" ||
    appState === "live-ready";

  const jobProgressText = useMemo(() => {
    if (!latestStatus) {
      return "Waiting for job updates...";
    }
    const total =
      latestStatus.progress_total > 0
        ? latestStatus.progress_total
        : totalSlides;
    const current = latestStatus.progress_current;
    const pct = total > 0 ? Math.round((current / total) * 100) : 0;
    return `${latestStatus.status} • ${current}/${total} (${pct}%)`;
  }, [latestStatus, totalSlides]);

  // Rebuild timeline whenever allSlides changes
  useEffect(() => {
    if (allSlides.length > 0) {
      setTimeline(buildPlaybackTimeline(allSlides));
    }
  }, [allSlides]);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    if (!file) {
      setUploadError("Please choose a .pptx file before uploading.");
      return;
    }

    setAppState("uploading");
    setUploadError(null);
    setJobError(null);
    setLatestStatus(null);
    setAllSlides([]);
    slidesRef.current = [];
    slideIndicesRef.current = new Set();
    setTimeline([]);
    setTotalSlides(0);
    setScriptResultFile(null);
    setJobId(null);
    setParseId("");

    try {
      if (mode === "live") {
        // Live Co-Present: parse PPTX structure + precompute branches
        const parseResult = await parsePptxOnly(file, {
          includeImagesBase64: true,
          flattenGroups: true,
          elementTypes: [],
        });
        setParseId(parseResult.parse_id);
        const liveSlides: SlideScript[] = parseResult.slides.map((s) => ({
          slide_index: s.slide_index,
          narrative_segments: [],
          summary: "",
          warnings: s.warnings,
          width_px: s.image?.width_px ?? 0,
          height_px: s.image?.height_px ?? 0,
          image_base64: s.image?.image_base64 ?? null,
        }));
        slidesRef.current = liveSlides;
        setAllSlides([...liveSlides]);
        setTotalSlides(parseResult.total_slides);
        setLiveSlideIndex(0);
        setBranchesData(null);

        // Connect SSE for branch precomputation progress (replaces polling)
        setAppState("precomputing");
        const abortCtrl = new AbortController();
        branchAbortRef.current = abortCtrl;

        // Initialize empty branches structure
        const liveSlidesCount = parseResult.total_slides;
        const branches: Record<number, BranchNode[]> = {};

        streamBranchEvents(
          parseResult.parse_id,
          {
            onBranchReady(slideIndex: number, nodes: BranchNode[]) {
              branches[slideIndex] = nodes;
              setBranchesData({
                parse_id: parseResult.parse_id,
                total_slides: liveSlidesCount,
                ready: Object.keys(branches).length === liveSlidesCount,
                branches: { ...branches },
              });
            },
            onDone() {
              setBranchesData((prev) =>
                prev
                  ? { ...prev, ready: true }
                  : {
                      parse_id: parseResult.parse_id,
                      total_slides: liveSlidesCount,
                      ready: true,
                      branches: { ...branches },
                    },
              );
              setAppState("live-ready");
            },
            onError(error: string) {
              console.warn(
                "[Branch SSE] failed, falling back to polling:",
                error,
              );
              // Fallback: switch to polling
              fallbackPollBranches(parseResult.parse_id, liveSlidesCount);
            },
          },
          abortCtrl.signal,
        );
      } else {
        // Auto-Present: full pipeline (parse + LLM + TTS)
        const submitResponse = await submitPptxScriptJob(file, {
          includeImagesBase64: true,
          flattenGroups: true,
          elementTypes: [],
        });
        setJobId(submitResponse.job_id);
        setAppState("job-pending");
        queueMicrotask(() => {
          setAppState("streaming");
        });
      }
    } catch (error) {
      setUploadError(
        error instanceof Error ? error.message : "Failed to submit job.",
      );
      setAppState("idle");
    }
  }

  function fallbackPollBranches(pid: string, _total: number): void {
    // SSE failed — fall back to polling every 2s
    const interval = setInterval(async () => {
      try {
        const bd = await fetchPrecomputedBranches(pid);
        setBranchesData(bd);
        if (bd.ready) {
          clearInterval(interval);
          setAppState("live-ready");
        }
      } catch {
        /* ignore */
      }
    }, 2000);
    branchAbortRef.current = null; // Clear the SSE abort controller
  }

  function resetToIdle(): void {
    live.stop();
    if (branchAbortRef.current) {
      branchAbortRef.current.abort();
      branchAbortRef.current = null;
    }
    setAppState("idle");
    setJobId(null);
    setLatestStatus(null);
    setJobError(null);
    setAllSlides([]);
    slidesRef.current = [];
    slideIndicesRef.current = new Set();
    setTimeline([]);
    setTotalSlides(0);
    setScriptResultFile(null);
    setParseId("");
    setBranchesData(null);
    setLiveSlideIndex(0);
  }

  // ---- SSE listener with auto-reconnect & deduplication ----
  // Keep SSE connected as long as the job is active, even if playback starts.
  const sseEnabled =
    (appState === "streaming" ||
      appState === "sliding" ||
      appState === "playing" ||
      appState === "paused") &&
    jobId != null;

  const sseState = useJobSse(jobId, sseEnabled, {
    onStatus(data: string) {
      try {
        const payload = JSON.parse(data) as PptxScriptSseEvent;
        console.log(
          "[SSE status]",
          payload.status.status,
          payload.status.progress_current,
          "/",
          payload.status.progress_total,
        );
        setLatestStatus(payload.status);
      } catch {
        setJobError("Failed to parse status event payload.");
        setAppState("idle");
      }
    },
    onSlideReady(data: string) {
      try {
        const payload = JSON.parse(data) as SlideReadySseEvent;
        // Debug: check audio_base64 status per segment
        const audioInfo = payload.slide.narrative_segments
          .map((s, i) =>
            s.audio_base64
              ? `seg${i}=${s.audio_base64.length}b`
              : `seg${i}=NO_AUDIO`,
          )
          .join(", ");
        console.log(
          "[SSE slide_ready] index=",
          payload.slide_index,
          "total=",
          payload.total_slides,
          "segments=",
          payload.slide.narrative_segments.length,
          "audio=[",
          audioInfo,
          "]",
          "has timeline?",
          timeline.length,
        );

        // Deduplicate by slide_index (SSE reconnect replays all slides)
        if (slideIndicesRef.current.has(payload.slide_index)) {
          console.log(
            "[SSE slide_ready] DUPLICATE skipped",
            payload.slide_index,
          );
          return;
        }
        slideIndicesRef.current.add(payload.slide_index);

        slidesRef.current = [...slidesRef.current, payload.slide];
        setAllSlides([...slidesRef.current]);
        setTotalSlides(payload.total_slides);

        // Stay in streaming until all slides are done
        // (no longer auto-transition to sliding on first slide)
      } catch (err) {
        console.error("[SSE slide_ready] parse error", err);
      }
    },
    onDone(data: string) {
      try {
        const payload = JSON.parse(data) as PptxScriptSseEvent;
        console.log(
          "[SSE done]",
          payload.status.status,
          "message=",
          payload.status.message,
          "error=",
          payload.status.error,
        );

        setLatestStatus(payload.status);

        if (payload.status.status === "done") {
          console.log(
            "[SSE] job completed successfully, has slides=",
            slidesRef.current.length,
          );
          setScriptResultFile(payload.status.message ?? "Completed");
          setAppState((prev) => {
            if (prev === "streaming" || prev === "sliding") {
              return mode === "live" ? "live-ready" : "ready-to-play";
            }
            return prev;
          });
          return;
        }

        setJobError(
          payload.status.error ?? payload.status.message ?? "Job failed.",
        );
        setAppState("idle");
      } catch (err) {
        console.error("[SSE done] parse error", err);
        setJobError("Failed to parse completion event payload.");
        setAppState("idle");
      }
    },
  });

  // Log SSE connection state changes
  useEffect(() => {
    console.log("[SSE connectionState]", sseState);
  }, [sseState]);

  // Sync live slide index from backend-driven transitions
  useEffect(() => {
    if (mode === "live" && live.currentSlideIndex >= 0) {
      setLiveSlideIndex(live.currentSlideIndex);
    }
  }, [live.currentSlideIndex, mode]);

  // Clean up branch SSE on unmount
  useEffect(() => {
    return () => {
      if (branchAbortRef.current) {
        branchAbortRef.current.abort();
        branchAbortRef.current = null;
      }
    };
  }, []);

  // Auto-play when all slides are generated (auto mode only).
  // Triggered when state transitions to "ready-to-play" — meaning all slides
  // from concurrent generation have arrived and the timeline is complete.
  useEffect(() => {
    if (mode !== "auto") return;
    if (
      appState === "ready-to-play" &&
      timeline.length > 0 &&
      !playback.isPlaying
    ) {
      playback.togglePlayPause();
      setAppState("playing");
    }
  }, [appState, timeline, playback, mode]);

  function handlePlayPause(): void {
    if (appState === "ready-to-play") {
      if (timeline.length === 0) {
        return;
      }
      playback.togglePlayPause();
      setAppState("playing");
      return;
    }

    if (appState === "playing") {
      if (!playback.isPlaying) {
        playback.togglePlayPause();
        setAppState("playing");
        return;
      }
      playback.togglePlayPause();
      setAppState("paused");
      return;
    }

    if (appState === "paused") {
      playback.togglePlayPause();
      setAppState("playing");
    }
  }

  function handlePrevious(): void {
    playback.playPrevious();
  }

  function handleNext(): void {
    playback.playNext();
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-6xl px-4 py-6 md:px-8 md:py-10">
        <AppTopBar title="GemmaSlide" subtitle="Presentation Viewer" />

        <header className={`rounded-xl bg-secondary p-6 md:p-8`}>
          <h1 className="text-3xl font-semibold tracking-[-0.01em] text-foreground md:text-4xl">
            Upload and Preview PPTX Slides
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground md:text-base">
            Upload a .pptx file, choose your mode, then present with AI
            assistance.
          </p>

          {/* Mode Selector */}
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              onClick={() => {
                if (appState === "idle") setMode("auto");
              }}
              className={`rounded-full px-5 py-2 text-sm font-medium transition ${
                mode === "auto"
                  ? "bg-primary text-primary-foreground"
                  : "border border-border bg-background text-foreground hover:bg-accent"
              }`}
            >
              Auto-Present
            </button>
            <button
              type="button"
              onClick={() => {
                if (appState === "idle") setMode("live");
              }}
              className={`rounded-full px-5 py-2 text-sm font-medium transition ${
                mode === "live"
                  ? "bg-primary text-primary-foreground"
                  : "border border-border bg-background text-foreground hover:bg-accent"
              }`}
            >
              Live Co-Present
            </button>
          </div>

          <form
            onSubmit={handleSubmit}
            className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-end"
          >
            <div className="grow">
              <label className="mb-2 block text-sm font-medium text-foreground">
                PPTX file
              </label>
              <input
                type="file"
                accept=".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                className="block w-full rounded-[18px] border border-border bg-accent px-4 py-3 text-sm text-foreground file:mr-3 file:rounded-full file:border-0 file:bg-secondary file:px-4 file:py-2 file:text-xs file:font-medium file:text-secondary-foreground"
              />
            </div>
            <button
              type="submit"
              disabled={!canSubmit}
              className="rounded-full bg-primary px-6 py-3 text-sm font-medium text-primary-foreground shadow-md transition hover:brightness-[0.98] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {appState === "uploading" ? "Uploading..." : "Upload PPTX"}
            </button>
          </form>

          {uploadError && (
            <div className="mt-4 rounded-[20px] border border-destructive bg-destructive/10 p-4 text-sm text-destructive">
              {uploadError}
            </div>
          )}

          {jobError && (
            <div className="mt-4 rounded-[20px] border border-destructive bg-destructive/10 p-4 text-sm text-destructive">
              {jobError}
            </div>
          )}

          {(appState === "job-pending" ||
            appState === "streaming" ||
            appState === "sliding" ||
            appState === "precomputing") && (
            <div className="mt-4 rounded-[20px] border border-border bg-background p-4 text-sm">
              <p className="font-medium text-foreground">
                {appState === "precomputing"
                  ? `Precomputing branches... ${branchesData ? Object.keys(branchesData.branches).length : 0}/${totalSlides} slides`
                  : appState === "sliding"
                    ? `Generating... ${allSlides.length}/${totalSlides} slides ready`
                    : "Job in progress"}
              </p>
              <p className="mt-1 text-muted-foreground">
                {appState === "precomputing"
                  ? "Analyzing slide content for live presentation..."
                  : appState === "sliding"
                    ? mode === "live"
                      ? `Slide ${allSlides.length} of ${totalSlides} ready — generating...`
                      : `Slide ${allSlides.length} of ${totalSlides} ready — generating all slides concurrently`
                    : jobProgressText}
              </p>
              {sseState === "connecting" && (
                <p className="mt-1 text-accent-foreground">
                  ⏳ Reconnecting to server...
                </p>
              )}
            </div>
          )}

          {(appState === "ready-to-play" ||
            appState === "playing" ||
            appState === "paused" ||
            appState === "live-ready" ||
            appState === "precomputing") && (
            <div className="mt-4 flex flex-wrap items-center gap-3">
              {appState === "precomputing" ? (
                <span className="text-sm text-muted-foreground">
                  ⏳ Preparing your presentation...
                </span>
              ) : (
                <>
                  {mode === "auto" && appState !== "live-ready" && (
                    <>
                      <button
                        type="button"
                        onClick={handlePlayPause}
                        className="rounded-full bg-primary px-6 py-3 text-sm font-medium text-primary-foreground"
                      >
                        {appState === "playing" ? "Pause" : "Play"}
                      </button>
                    </>
                  )}
                  {mode === "live" && (
                    <>
                      {live.status === "idle" && (
                        <button
                          type="button"
                          onClick={() => live.start(parseId)}
                          className="rounded-full bg-green-600 px-6 py-3 text-sm font-medium text-white hover:bg-green-700"
                        >
                          Start Mic
                        </button>
                      )}
                      {live.status === "recording" && (
                        <button
                          type="button"
                          onClick={live.stop}
                          className="rounded-full bg-red-600 px-6 py-3 text-sm font-medium text-white hover:bg-red-700"
                        >
                          Stop
                        </button>
                      )}
                      {live.status === "connecting" && (
                        <span className="rounded-full bg-blue-100 px-4 py-2 text-sm font-medium text-blue-700">
                          Connecting...
                        </span>
                      )}
                      {live.status === "error" && (
                        <button
                          type="button"
                          onClick={() => live.start(parseId)}
                          className="rounded-full bg-amber-600 px-6 py-3 text-sm font-medium text-white hover:bg-amber-700"
                        >
                          Retry
                        </button>
                      )}
                    </>
                  )}
                </>
              )}
              <button
                type="button"
                onClick={resetToIdle}
                className="rounded-full border border-border px-6 py-3 text-sm font-medium text-foreground"
              >
                Reset
              </button>
              {scriptResultFile && (
                <span className="text-sm text-muted-foreground">
                  {scriptResultFile} • {timeline.length} segments •{" "}
                  {allSlides.length} slides
                </span>
              )}
            </div>
          )}
        </header>

        <section className={`rounded-xl border bg-card mt-5 p-4 md:p-6`}>
          {/* Empty state */}
          {timeline.length === 0 &&
            appState !== "playing" &&
            appState !== "paused" &&
            appState !== "sliding" &&
            appState !== "live-ready" &&
            appState !== "precomputing" && (
              <div className="grid min-h-[360px] place-items-center rounded-[20px] border border-dashed border-border bg-secondary p-4 text-center text-sm text-muted-foreground">
                Upload a PPTX file to generate script-guided playback.
              </div>
            )}

          {/* Auto-Present mode: ScriptPlaybackPanel */}
          {mode === "auto" &&
            (appState === "playing" ||
              appState === "paused" ||
              appState === "sliding") && (
              <ScriptPlaybackPanel
                activeSegment={playback.activeSegment?.segment ?? null}
                currentSegmentIndex={playback.currentSegmentIndex}
                totalSegments={timeline.length}
                activeSlide={activeSlide}
                playbackState={{
                  isPlaying: playback.isPlaying,
                  canGoPrevious: playback.canGoPrevious,
                  canGoNext: playback.canGoNext,
                }}
                onPlayPause={handlePlayPause}
                onPrevious={handlePrevious}
                onNext={handleNext}
              />
            )}

          {/* Live Co-Present mode */}
          {mode === "live" &&
            appState === "live-ready" &&
            (() => {
              const currentSlide = allSlides[liveSlideIndex] ?? null;
              const currentBranches =
                branchesData?.branches[liveSlideIndex] ?? [];
              const bboxes = flattenBboxes(currentBranches);
              const matchedBbox = live.matchResult
                ? (bboxes.find(
                    (bb) => bb.branch_id === live.matchResult?.branch_id,
                  ) ?? null)
                : null;

              return (
                <>
                  <div className="grid gap-6 lg:grid-cols-[5fr_3fr]">
                    {/* ── Left: Slide Preview ── */}
                    <div className="rounded-3xl overflow-hidden border border-border bg-black">
                      <div
                        className="relative"
                        style={{
                          aspectRatio: currentSlide
                            ? `${currentSlide.width_px}/${currentSlide.height_px}`
                            : "16/9",
                        }}
                      >
                        {currentSlide?.image_base64 ? (
                          <img
                            src={currentSlide.image_base64}
                            alt={`Slide ${liveSlideIndex + 1}`}
                            className="w-full h-full object-contain"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-gray-500 text-sm">
                            No slide image
                          </div>
                        )}
                        {/* Only current match bbox overlay */}
                        {matchedBbox &&
                          (() => {
                            const [ymin, xmin, ymax, xmax] =
                              matchedBbox.bbox_1000;
                            return (
                              <div
                                className="absolute pointer-events-none animate-pulse"
                                style={{
                                  top: `${(ymin / 1000) * 100}%`,
                                  left: `${(xmin / 1000) * 100}%`,
                                  height: `${((ymax - ymin) / 1000) * 100}%`,
                                  width: `${((xmax - xmin) / 1000) * 100}%`,
                                  background:
                                    OVERLAY_COLORS[matchedBbox.action_type],
                                  border: `3px solid ${OVERLAY_BORDER[matchedBbox.action_type]}`,
                                  borderRadius: "6px",
                                  boxShadow: `0 0 24px ${OVERLAY_BORDER[matchedBbox.action_type]}50`,
                                }}
                              />
                            );
                          })()}
                      </div>
                      {/* Slide dots */}
                      {allSlides.length > 1 && (
                        <div className="flex items-center justify-center gap-1.5 p-3 bg-secondary">
                          {allSlides.map((_, i) => (
                            <button
                              key={i}
                              onClick={() => setLiveSlideIndex(i)}
                              className={`shrink-0 w-2.5 h-2.5 rounded-full transition-all ${
                                i === liveSlideIndex
                                  ? "bg-primary scale-125"
                                  : "bg-border hover:bg-border"
                              }`}
                              title={`Slide ${i + 1}`}
                            />
                          ))}
                        </div>
                      )}
                    </div>

                    {/* ── Right: Live Branch List (fixed-position, no jumping) ── */}
                    <LiveBranchList
                      branches={currentBranches}
                      matchResult={live.matchResult}
                      trackResult={live.trackResult}
                      status={live.status}
                    />
                  </div>

                  {/* ── Raw ASR (collapsed) ── */}
                  {live.status === "recording" && live.asrText && (
                    <details className="rounded-2xl border border-border bg-background p-4">
                      <summary className="text-xs font-medium text-gray-400 cursor-pointer select-none">
                        🎙️ Raw Transcript
                      </summary>
                      <p className="mt-2 text-xs text-gray-500 font-mono leading-relaxed">
                        {live.asrText}
                      </p>
                    </details>
                  )}
                </>
              );
            })()}
        </section>
      </div>
    </div>
  );
}
