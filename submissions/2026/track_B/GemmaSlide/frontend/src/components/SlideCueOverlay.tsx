import { scaleBBoxToDisplay } from "../lib/scale-bbox";
import { CueActionType, type BBoxPx } from "../types";

interface SlideCueOverlayProps {
  slideImageBase64: string | null;
  originalWidth: number;
  originalHeight: number;
  displayWidth: number;
  displayHeight: number;
  cueActionType: CueActionType;
  targetBBoxPx: BBoxPx | null;
}

export function SlideCueOverlay({
  slideImageBase64,
  originalWidth,
  originalHeight,
  displayWidth,
  displayHeight,
  cueActionType,
  targetBBoxPx,
}: SlideCueOverlayProps) {
  if (!slideImageBase64 || !targetBBoxPx || cueActionType === CueActionType.NONE) {
    return null;
  }

  const bbox = scaleBBoxToDisplay(
    targetBBoxPx,
    originalWidth,
    originalHeight,
    displayWidth,
    displayHeight,
  );

  const centerX = bbox.x + bbox.width / 2;
  const centerY = bbox.y + bbox.height / 2;
  const radius = Math.max(bbox.width, bbox.height) / 2;

  return (
    <div className="pointer-events-none absolute inset-0">
      <svg width="100%" height="100%" viewBox={`0 0 ${displayWidth} ${displayHeight}`}>
        {cueActionType === CueActionType.HIGHLIGHT && (
          <rect
            x={bbox.x}
            y={bbox.y}
            width={bbox.width}
            height={bbox.height}
            fill="rgba(103, 80, 164, 0.4)"
            stroke="rgb(103, 80, 164)"
            strokeWidth={2}
          />
        )}

        {cueActionType === CueActionType.CIRCLE && (
          <circle
            cx={centerX}
            cy={centerY}
            r={radius}
            fill="transparent"
            stroke="rgb(103, 80, 164)"
            strokeWidth={3}
          />
        )}

        {cueActionType === CueActionType.LASER && (
          <>
            <circle
              cx={centerX}
              cy={centerY}
              r={6}
              fill="rgb(103, 80, 164)"
              opacity={0.9}
            />
            <circle
              cx={centerX}
              cy={centerY}
              r={14}
              fill="none"
              stroke="rgb(103, 80, 164)"
              strokeWidth={2}
              opacity={0.6}
              className="animate-ping"
            />
          </>
        )}
      </svg>
    </div>
  );
}
