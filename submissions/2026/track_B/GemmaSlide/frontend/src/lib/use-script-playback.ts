import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { NarrativeSegment, SlideScript } from "../types";

const MIN_SEGMENT_DELAY_MS = 1000;

export interface PlaybackTimelineItem {
  slideIndex: number;
  segmentIndex: number;
  insertionIndex: number;
  segment: NarrativeSegment;
  slide: SlideScript;
  delayMs: number;
}

function toDelayMs(
  current: PlaybackTimelineItem,
  next: PlaybackTimelineItem,
): number {
  const deltaSeconds =
    next.segment.estimated_start_seconds -
    current.segment.estimated_start_seconds;
  const computed = Math.round(deltaSeconds * 1000);
  return computed > 0 ? computed : MIN_SEGMENT_DELAY_MS;
}

export function buildPlaybackTimeline(
  slides: SlideScript[],
): PlaybackTimelineItem[] {
  const flattened: PlaybackTimelineItem[] = [];
  let insertionIndex = 0;

  for (const slide of slides) {
    for (
      let segmentIndex = 0;
      segmentIndex < slide.narrative_segments.length;
      segmentIndex += 1
    ) {
      flattened.push({
        slideIndex: slide.slide_index,
        segmentIndex,
        insertionIndex,
        segment: slide.narrative_segments[segmentIndex],
        slide,
        delayMs: MIN_SEGMENT_DELAY_MS,
      });
      insertionIndex += 1;
    }
  }

  flattened.sort((left, right) => {
    if (left.slideIndex !== right.slideIndex) {
      return left.slideIndex - right.slideIndex;
    }

    const deltaStart =
      left.segment.estimated_start_seconds -
      right.segment.estimated_start_seconds;
    if (deltaStart !== 0) {
      return deltaStart;
    }

    return left.insertionIndex - right.insertionIndex;
  });

  for (let index = 0; index < flattened.length; index += 1) {
    const current = flattened[index];
    const next = flattened[index + 1];
    current.delayMs = next ? toDelayMs(current, next) : MIN_SEGMENT_DELAY_MS;
  }

  return flattened;
}

export interface UseScriptPlaybackResult {
  currentSegmentIndex: number;
  isPlaying: boolean;
  isAudioPlaying: boolean;
  hasAudio: boolean;
  activeSegment: PlaybackTimelineItem | null;
  activeSlideIndex: number;
  canGoPrevious: boolean;
  canGoNext: boolean;
  readyCount: number;
  playNext: () => void;
  playPrevious: () => void;
  togglePlayPause: () => void;
  appendSlides: (newSlides: SlideScript[]) => void;
}

export function useScriptPlayback(
  timeline: PlaybackTimelineItem[],
): UseScriptPlaybackResult {
  const [currentSegmentIndex, setCurrentSegmentIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isAudioPlaying, setIsAudioPlaying] = useState(false);

  // Track previous timeline length so we don't reset index on append
  const prevTimelineLengthRef = useRef(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const currentAudioUrlRef = useRef<string | null>(null);
  // Refs for values that the audio onEnded callback needs to read fresh
  // without re-triggering the audio effect when they change (e.g. when
  // new slides are appended via SSE while audio is already playing).
  const canGoNextRef = useRef(false);
  const maxIndexRef = useRef(0);

  const totalSegments = timeline.length;
  const maxIndex = Math.max(totalSegments - 1, 0);
  const boundedSegmentIndex = Math.min(
    Math.max(currentSegmentIndex, 0),
    maxIndex,
  );

  const activeSegment = useMemo(() => {
    if (totalSegments === 0) {
      return null;
    }
    return timeline[boundedSegmentIndex] ?? null;
  }, [boundedSegmentIndex, timeline, totalSegments]);

  const canGoPrevious = boundedSegmentIndex > 0;
  const canGoNext = boundedSegmentIndex < totalSegments - 1;
  const activeSlideIndex = activeSegment?.slideIndex ?? 0;
  const hasAudio =
    activeSegment?.segment.audio_base64 != null &&
    activeSegment.segment.audio_base64.length > 0;

  // Compute readyCount: number of slides fully loaded in timeline
  // Keep refs fresh so onEnded always reads the latest values
  canGoNextRef.current = canGoNext;
  maxIndexRef.current = maxIndex;

  const readyCount = useMemo(() => {
    if (timeline.length === 0) return 0;
    const lastItem = timeline[timeline.length - 1];
    return lastItem.slideIndex + 1;
  }, [timeline]);

  // --- Audio playback ---
  // Play audio when the segment or its audio content changes.
  // Depends on stable content identifiers rather than object references,
  // so that appending slides via SSE does NOT restart the current audio.
  useEffect(() => {
    const segment = activeSegment?.segment;
    if (!segment?.audio_base64 || !isPlaying) {
      if (!segment?.audio_base64 && isPlaying) {
        console.log(
          "[Audio] no audio_base64 for segment",
          boundedSegmentIndex,
          "text=",
          segment?.text?.slice(0, 40),
        );
      }
      // Cleanup if no audio or paused
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      if (currentAudioUrlRef.current) {
        URL.revokeObjectURL(currentAudioUrlRef.current);
        currentAudioUrlRef.current = null;
      }
      setIsAudioPlaying(false);
      return;
    }

    // Decode base64 to blob
    const audioUrl = segment.audio_base64; // data URI
    console.log(
      "[Audio] playing segment",
      boundedSegmentIndex,
      "audioUrl length=",
      audioUrl.length,
      "text=",
      segment.text.slice(0, 40),
    );
    const audio = new Audio(audioUrl);
    audioRef.current = audio;
    currentAudioUrlRef.current = audioUrl;

    const onEnded = () => {
      console.log("[Audio] ended, canGoNext=", canGoNextRef.current);
      setIsAudioPlaying(false);
      if (canGoNextRef.current) {
        setCurrentSegmentIndex((current) => {
          const nextIndex = Math.min(current + 1, maxIndexRef.current);
          if (nextIndex >= maxIndexRef.current) {
            console.log("[Audio] reached last segment, stopping");
            setIsPlaying(false);
          }
          return nextIndex;
        });
      } else {
        // More slides may be on the way via SSE.
        // Don't stop playback — keep isPlaying=true so the delay effect
        // can auto-advance when canGoNext becomes true (more slides loaded).
        // The audio effect's deps are stable, so it won't re-trigger.
        console.log(
          "[Audio] at end of available content, waiting for more slides...",
        );
        // Clean up finished audio element; new one created when next segment plays
        audioRef.current = null;
      }
    };

    audio.addEventListener("ended", onEnded);
    audio
      .play()
      .then(() => {
        console.log(
          "[Audio] play started successfully for segment",
          boundedSegmentIndex,
        );
        setIsAudioPlaying(true);
      })
      .catch((err) => {
        console.log(
          "[Audio] play() failed:",
          err?.message,
          "- falling back to delay",
        );
        // Autoplay may be blocked; fall through to delay-based
        setIsAudioPlaying(false);
      });

    return () => {
      audio.removeEventListener("ended", onEnded);
      audio.pause();
      audioRef.current = null;
    };
  }, [
    // Use stable identifiers — NOT `activeSegment` (which is a new object
    // reference whenever slides are appended via SSE, causing audio restart).
    activeSegment?.segmentIndex,
    activeSegment?.segment.audio_base64,
    isPlaying,
    boundedSegmentIndex,
  ]);

  // --- Delay-based fallback (when no audio or audio failed) ---
  useEffect(() => {
    if (!isPlaying || !activeSegment) {
      console.log("[Delay] not playing or no active segment", {
        isPlaying,
        hasActive: !!activeSegment,
      });
      return;
    }

    // If this segment has audio that is playing, skip the delay timer
    if (hasAudio && isAudioPlaying) {
      console.log("[Delay] audio is playing, skipping delay timer");
      return;
    }

    if (!canGoNext) {
      console.log("[Delay] at last segment, stopping");
      return;
    }

    const timeout = window.setTimeout(() => {
      setCurrentSegmentIndex((current) => {
        const nextIndex = Math.min(current + 1, maxIndex);
        if (nextIndex >= maxIndex) {
          setIsPlaying(false);
        }
        return nextIndex;
      });
    }, activeSegment.delayMs);

    return () => {
      window.clearTimeout(timeout);
    };
  }, [
    activeSegment?.segmentIndex,
    activeSegment?.delayMs,
    canGoNext,
    hasAudio,
    isAudioPlaying,
    isPlaying,
    maxIndex,
  ]);

  // --- Don't reset index when timeline grows ---
  useEffect(() => {
    const prevLen = prevTimelineLengthRef.current;
    if (timeline.length > prevLen && prevLen > 0) {
      console.log(
        "[Playback] timeline appended:",
        prevLen,
        "->",
        timeline.length,
      );
      // Timeline was appended — keep current index
      prevTimelineLengthRef.current = timeline.length;
      return;
    }
    // Fresh timeline (new job) — reset to 0
    if (timeline.length === 0) {
      setCurrentSegmentIndex(0);
    }
    if (timeline.length !== prevLen) {
      console.log(
        "[Playback] timeline changed:",
        prevLen,
        "->",
        timeline.length,
        "(fresh=",
        prevLen === 0,
        ")",
      );
    }
    prevTimelineLengthRef.current = timeline.length;
  }, [timeline.length]);

  const playNext = useCallback(() => {
    setCurrentSegmentIndex((current) => {
      const boundedCurrent = Math.min(Math.max(current, 0), maxIndex);
      return Math.min(boundedCurrent + 1, maxIndex);
    });
  }, [maxIndex]);

  const playPrevious = useCallback(() => {
    setCurrentSegmentIndex((current) => {
      const boundedCurrent = Math.min(Math.max(current, 0), maxIndex);
      return Math.max(boundedCurrent - 1, 0);
    });
  }, [maxIndex]);

  const togglePlayPause = useCallback(() => {
    setIsPlaying((current) => {
      if (totalSegments === 0) {
        console.log("[Playback] togglePlayPause: no segments");
        return false;
      }
      if (!current && boundedSegmentIndex >= maxIndex) {
        console.log("[Playback] togglePlayPause: already at end, cannot play");
        return false;
      }
      // Pause audio when pausing playback
      if (current && audioRef.current) {
        audioRef.current.pause();
        setIsAudioPlaying(false);
      }
      console.log(
        "[Playback] togglePlayPause:",
        current ? "pausing" : "playing",
      );
      return !current;
    });
  }, [boundedSegmentIndex, maxIndex, totalSegments]);

  const appendSlides = useCallback((_newSlides: SlideScript[]) => {
    // This is handled by the parent via the timeline prop
    // Exposed for API consistency
  }, []);

  return {
    currentSegmentIndex: boundedSegmentIndex,
    isPlaying,
    isAudioPlaying,
    hasAudio,
    activeSegment,
    activeSlideIndex,
    canGoPrevious,
    canGoNext,
    readyCount,
    playNext,
    playPrevious,
    togglePlayPause,
    appendSlides,
  };
}
