import type React from "react";

import Teleprompter from "../components/Teleprompter";
import { useLiveSession } from "../lib/use-live-session";

const DebugLivePage: React.FC = () => {
  const {
    status,
    asrText,
    asrVisible,
    lastSentence,
    suggestion,
    toggleAsrVisible,
    start,
    stop,
  } = useLiveSession();

  const isRecording = status === "recording";
  const isConnecting = status === "connecting";
  const isError = status === "error";

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Live ASR Debug</h1>

      {/* Controls */}
      <div className="flex items-center gap-4">
        <button
          onClick={isRecording ? stop : () => start("")}
          disabled={isConnecting}
          className={`px-5 py-2.5 rounded-full font-semibold text-sm tracking-wide transition-colors ${
            isRecording
              ? "bg-red-600 text-white hover:bg-red-700"
              : isError
                ? "bg-amber-600 text-white hover:bg-amber-700"
                : "bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          }`}
        >
          {isConnecting
            ? "Connecting…"
            : isRecording
              ? "Stop"
              : isError
                ? "Retry"
                : "Start Mic"}
        </button>

        <button
          onClick={toggleAsrVisible}
          className="px-4 py-2.5 rounded-full text-sm font-medium border border-gray-300 hover:bg-gray-50 transition-colors"
        >
          {asrVisible ? "Hide ASR" : "Show ASR"}
        </button>

        <span
          className={`ml-auto text-xs uppercase tracking-widest font-semibold px-2 py-1 rounded ${
            isRecording
              ? "bg-green-100 text-green-800"
              : isConnecting
                ? "bg-blue-100 text-blue-800"
                : isError
                  ? "bg-red-100 text-red-800"
                  : "bg-gray-100 text-gray-500"
          }`}
        >
          {status}
        </span>
      </div>

      {/* ASR Text Display */}
      {asrVisible && (
        <div className="rounded-xl border border-gray-200 bg-white p-5 min-h-[120px]">
          <p className="text-sm text-gray-400 mb-2">
            {isRecording ? "Live Transcription" : "Transcription"}
          </p>
          <p className="text-lg leading-relaxed whitespace-pre-wrap break-words">
            {asrText || (
              <span className="text-gray-300 italic">Waiting for speech…</span>
            )}
          </p>
        </div>
      )}

      {/* Last Sentence Info */}
      {lastSentence && (
        <div className="rounded-lg border border-gray-100 bg-gray-50 p-4 text-sm text-gray-600 space-y-1">
          <div>
            <span className="font-medium">Last Sentence:</span>{" "}
            {lastSentence.text}
          </div>
          <div>
            <span className="font-medium">Time:</span> {lastSentence.begin_time}
            s – {lastSentence.end_time}s
          </div>
          <div>
            <span className="font-medium">End:</span>{" "}
            {String(lastSentence.is_sentence_end)}
          </div>
        </div>
      )}

      {/* Teleprompter / AI Suggestion */}
      <div className="rounded-lg border border-gray-100 bg-gray-50 p-4">
        <p className="text-sm text-gray-400 mb-2">AI Teleprompter</p>
        <Teleprompter
          suggestion={suggestion?.next_suggestion ?? null}
          loading={isRecording && lastSentence != null}
        />
      </div>

      {/* Error State */}
      {isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Microphone access failed. Please allow mic permissions and try again.
        </div>
      )}
    </div>
  );
};

export default DebugLivePage;
