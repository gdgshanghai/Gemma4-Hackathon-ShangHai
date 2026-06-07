import type { ShapeElement, SlideResult } from "../types";

export const EMPTY_SLIDES: SlideResult[] = [];

export function colorFromType(typeName: string): string {
  let hash = 0;
  for (let i = 0; i < typeName.length; i += 1) {
    hash = typeName.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash % 360);
  return `hsl(${hue} 80% 55%)`;
}

export function formatBBox(
  element: ShapeElement,
  mode: "px" | "norm" | "emu",
): string {
  if (mode === "px") {
    if (!element.bbox_px) {
      return "N/A";
    }
    const b = element.bbox_px;
    return `x:${b.x} y:${b.y} w:${b.width} h:${b.height}`;
  }

  if (mode === "norm") {
    const b = element.bbox_norm;
    return `x:${b.x.toFixed(3)} y:${b.y.toFixed(3)} w:${b.width.toFixed(3)} h:${b.height.toFixed(3)}`;
  }

  const b = element.bbox_emu;
  return `x:${b.x} y:${b.y} w:${b.width} h:${b.height}`;
}

export function computeCanvasSize(
  slide: SlideResult,
  zoom: number,
): { width: number; height: number } {
  const baseWidth = slide.image?.width_px ?? 960;
  const ratio =
    slide.slide_width_emu > 0
      ? slide.slide_height_emu / slide.slide_width_emu
      : 0.5625;
  const baseHeight =
    slide.image?.height_px ?? Math.max(1, Math.round(baseWidth * ratio));

  return {
    width: Math.max(1, Math.round(baseWidth * zoom)),
    height: Math.max(1, Math.round(baseHeight * zoom)),
  };
}
