import type { BBoxPx } from "../types";

export function scaleBBoxToDisplay(
  bboxPx: BBoxPx,
  sourceWidth: number,
  sourceHeight: number,
  displayWidth: number,
  displayHeight: number,
): BBoxPx {
  if (sourceWidth <= 0 || sourceHeight <= 0) {
    return {
      x: 0,
      y: 0,
      width: 0,
      height: 0,
    };
  }

  const scaleX = displayWidth / sourceWidth;
  const scaleY = displayHeight / sourceHeight;

  return {
    x: Math.round(bboxPx.x * scaleX),
    y: Math.round(bboxPx.y * scaleY),
    width: Math.round(bboxPx.width * scaleX),
    height: Math.round(bboxPx.height * scaleY),
  };
}
