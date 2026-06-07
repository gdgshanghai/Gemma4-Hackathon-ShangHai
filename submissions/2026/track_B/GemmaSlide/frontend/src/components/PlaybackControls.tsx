import { Button } from "@/components/ui/button";

interface PlaybackControlsProps {
  isPlaying: boolean;
  canGoPrevious: boolean;
  canGoNext: boolean;
  onTogglePlayPause: () => void;
  onPrevious: () => void;
  onNext: () => void;
}

export function PlaybackControls({
  isPlaying,
  canGoPrevious,
  canGoNext,
  onTogglePlayPause,
  onPrevious,
  onNext,
}: PlaybackControlsProps) {
  return (
    <div className="flex items-center justify-center gap-3 rounded-[18px] border bg-card p-3">
      <Button variant="outline" disabled={!canGoPrevious} onClick={onPrevious}>
        Previous
      </Button>

      <Button onClick={onTogglePlayPause}>
        {isPlaying ? "Pause" : "Play"}
      </Button>

      <Button variant="outline" disabled={!canGoNext} onClick={onNext}>
        Next
      </Button>
    </div>
  );
}
