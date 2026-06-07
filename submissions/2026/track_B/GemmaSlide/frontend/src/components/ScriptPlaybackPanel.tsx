import { PlaybackCaption } from "./PlaybackCaption";
import { PlaybackControls } from "./PlaybackControls";
import { SlideCueOverlay } from "./SlideCueOverlay";
import {
  CueActionType,
  type NarrativeSegment,
  type SlideScript,
} from "../types";

interface ScriptPlaybackPanelProps {
  activeSegment: NarrativeSegment | null;
  currentSegmentIndex: number;
  totalSegments: number;
  activeSlide: SlideScript | null;
  playbackState: {
    isPlaying: boolean;
    canGoPrevious: boolean;
    canGoNext: boolean;
  };
  onPlayPause: () => void;
  onPrevious: () => void;
  onNext: () => void;
}

export function ScriptPlaybackPanel({
  activeSegment,
  currentSegmentIndex,
  totalSegments,
  activeSlide,
  playbackState,
  onPlayPause,
  onPrevious,
  onNext,
}: ScriptPlaybackPanelProps) {
  const segmentText = activeSegment?.text ?? "No segments";
  const captionIndex = totalSegments > 0 ? currentSegmentIndex : -1;

  return (
    <section className="grid gap-4">
      <PlaybackCaption
        segmentText={segmentText}
        currentIndex={captionIndex}
        totalSegments={totalSegments}
      />

      <div className="rounded-[18px] border bg-muted/50 p-3">
        {!activeSlide && (
          <div className="grid min-h-[280px] place-items-center text-sm text-muted-foreground">
            No slide data
          </div>
        )}

        {activeSlide && (
          <div className="relative mx-auto w-fit">
            {activeSlide.image_base64 && (
              <img
                src={activeSlide.image_base64}
                alt={`Slide ${activeSlide.slide_index}`}
                className="block max-h-[72vh] w-auto max-w-full rounded-[12px] object-contain"
              />
            )}

            <SlideCueOverlay
              slideImageBase64={activeSlide.image_base64}
              originalWidth={activeSlide.width_px}
              originalHeight={activeSlide.height_px}
              displayWidth={activeSlide.width_px}
              displayHeight={activeSlide.height_px}
              cueActionType={
                activeSegment?.visual_cue.action_type ?? CueActionType.NONE
              }
              targetBBoxPx={activeSegment?.visual_cue.bbox_px ?? null}
            />
          </div>
        )}
      </div>

      <PlaybackControls
        isPlaying={playbackState.isPlaying}
        canGoPrevious={playbackState.canGoPrevious}
        canGoNext={playbackState.canGoNext}
        onTogglePlayPause={onPlayPause}
        onPrevious={onPrevious}
        onNext={onNext}
      />
    </section>
  );
}
