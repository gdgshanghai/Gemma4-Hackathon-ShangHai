import { useCallback, useEffect, useRef, useState } from "react";

import { buildApiEndpoint } from "../api";
import { MicCapture, pcmToBase64 } from "./audio-capture";
import type {
  AsrSentence,
  BranchMatchResult,
  BranchTrackResult,
  LiveSessionStatus,
  LiveWsMessage,
  ScriptSuggestion,
} from "../types";

const WS_URL = buildApiEndpoint("/api/v1/ws/live").replace(/^http/, "ws");

interface UseLiveSessionResult {
  status: LiveSessionStatus;
  asrText: string;
  asrVisible: boolean;
  lastSentence: AsrSentence | null;
  suggestion: ScriptSuggestion | null;
  matchResult: BranchMatchResult | null;
  trackResult: BranchTrackResult | null;
  currentSlideIndex: number;
  toggleAsrVisible: () => void;
  start: (parseId: string) => Promise<void>;
  stop: () => void;
}

interface LiveSessionCallbacks {
  onMatch?: (branchId: string) => void;
  onTransition?: (newSlideIndex: number) => void;
}

export function useLiveSession(
  callbacks?: LiveSessionCallbacks,
): UseLiveSessionResult {
  const [status, setStatus] = useState<LiveSessionStatus>("idle");
  const [asrText, setAsrText] = useState("");
  const [asrVisible, setAsrVisible] = useState(true);
  const [lastSentence, setLastSentence] = useState<AsrSentence | null>(null);
  const [suggestion, setSuggestion] = useState<ScriptSuggestion | null>(null);
  const [matchResult, setMatchResult] = useState<BranchMatchResult | null>(
    null,
  );
  const [trackResult, setTrackResult] = useState<BranchTrackResult | null>(
    null,
  );
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const micRef = useRef<MicCapture | null>(null);
  const statusRef = useRef<LiveSessionStatus>("idle");

  // Store callbacks in refs to avoid stale closures in onmessage
  const onMatchRef = useRef(callbacks?.onMatch);
  const onTransitionRef = useRef(callbacks?.onTransition);
  onMatchRef.current = callbacks?.onMatch;
  onTransitionRef.current = callbacks?.onTransition;

  // Track previous values for change detection inside onmessage
  const prevMatchIdRef = useRef<string | null>(null);

  const toggleAsrVisible = useCallback(() => setAsrVisible((v) => !v), []);

  const sendAudioChunk = useCallback((int16: Int16Array) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(
      JSON.stringify({ type: "audio", audio_base64: pcmToBase64(int16) }),
    );
  }, []);

  const stop = useCallback(() => {
    micRef.current?.stop();
    micRef.current = null;
    wsRef.current?.close();
    wsRef.current = null;
    setStatus("idle");
    statusRef.current = "idle";
    setSuggestion(null);
    setLastSentence(null);
    setMatchResult(null);
    setTrackResult(null);
    setAsrText("");
    setCurrentSlideIndex(0);
  }, []);

  const start = useCallback(
    async (parseId: string) => {
      if (statusRef.current !== "idle") return;

      setStatus("connecting");
      statusRef.current = "connecting";
      setAsrText("");
      setSuggestion(null);
      setLastSentence(null);
      setCurrentSlideIndex(0);

      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        // Send parse_id so backend can look up slides from cache
        ws.send(JSON.stringify({ type: "start", parse_id: parseId }));
      };

      ws.onmessage = (event: MessageEvent) => {
        try {
          const msg: LiveWsMessage = JSON.parse(event.data as string);

          if (msg.sentence) {
            if (msg.type === "asr_sentence_end") {
              setAsrText(msg.sentence.text);
              setLastSentence(msg.sentence);
              setSuggestion(null); // clear old suggestion while waiting for new one
            } else if (msg.type === "asr_intermediate") {
              setAsrText(msg.sentence.text);
            }
          }

          if (msg.type === "suggestion" && msg.suggestion) {
            setSuggestion(msg.suggestion);
            setLastSentence(null);
          }

          if (msg.type === "branch_match") {
            if (msg.match_result) {
              setMatchResult(msg.match_result);
              // Fire onMatch callback IMMEDIATELY (before React re-render)
              const newId = msg.match_result.branch_id;
              if (newId && newId !== prevMatchIdRef.current) {
                onMatchRef.current?.(newId);
              }
              prevMatchIdRef.current = newId;
            }
            if (msg.track_result) {
              setTrackResult(msg.track_result);
            }
          }

          // Backend pushed a slide change (clean transition — wipe old match/track)
          if (msg.type === "slide_change") {
            setMatchResult(null);
            setTrackResult(null);
            setCurrentSlideIndex(msg.slide_index ?? 0);
          }

          // After START is sent, begin mic capture once
          if (statusRef.current === "connecting" && msg.type !== "error") {
            // Mic start is deferred to next tick so START is processed
          }
        } catch {
          // ignore parse errors
        }
      };

      // Defer mic start to allow START message to be sent first
      let micStarted = false;
      const startMic = async () => {
        if (micStarted) return;
        micStarted = true;
        try {
          const mic = new MicCapture();
          micRef.current = mic;
          await mic.start(sendAudioChunk);
          setStatus("recording");
          statusRef.current = "recording";
        } catch (err) {
          console.error("Mic error:", err);
          setStatus("error");
          statusRef.current = "error";
        }
      };

      // Start mic after a short delay to let START propagate
      const micTimer = setTimeout(startMic, 500);

      ws.onclose = () => {
        clearTimeout(micTimer);
        if (statusRef.current === "recording") {
          micRef.current?.stop();
          micRef.current = null;
        }
        if (statusRef.current !== "idle") {
          setStatus("idle");
          statusRef.current = "idle";
        }
      };

      ws.onerror = () => {
        clearTimeout(micTimer);
        setStatus("error");
        statusRef.current = "error";
      };
    },
    [sendAudioChunk],
  );

  useEffect(() => {
    return () => {
      micRef.current?.stop();
      wsRef.current?.close();
    };
  }, []);

  return {
    status,
    asrText,
    asrVisible,
    lastSentence,
    suggestion,
    matchResult,
    trackResult,
    currentSlideIndex,
    toggleAsrVisible,
    start,
    stop,
  };
}
