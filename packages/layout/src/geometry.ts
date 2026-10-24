import type { Box, Format, Point } from "@flow/schema";

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export function canvasRect(format: Format): Rect {
  return { x: 0, y: 0, width: format.width, height: format.height };
}

export function safeAreaRect(format: Format): Rect {
  const zone = format.safeZone;
  return {
    x: zone.left,
    y: zone.top,
    width: format.width - zone.left - zone.right,
    height: format.height - zone.top - zone.bottom,
  };
}

function place(start: number, size: number, item: number, offset: number, mode: "start" | "center" | "end"): number {
  if (mode === "start") return start + offset;
  if (mode === "end") return start + size - item - offset;
  return start + (size - item) / 2 + offset;
}

const HORIZONTAL: Record<Box["anchor"], "start" | "center" | "end"> = {
  "top-left": "start",
  left: "start",
  "bottom-left": "start",
  top: "center",
  center: "center",
  bottom: "center",
  "top-right": "end",
  right: "end",
  "bottom-right": "end",
};

const VERTICAL: Record<Box["anchor"], "start" | "center" | "end"> = {
  "top-left": "start",
  top: "start",
  "top-right": "start",
  left: "center",
  center: "center",
  right: "center",
  "bottom-left": "end",
  bottom: "end",
  "bottom-right": "end",
};

/** Zet een relatieve box om naar pixels binnen de safe area, of binnen het canvas bij bleed. */
export function boxToRect(box: Box, format: Format): Rect {
  const container = box.bleed ? canvasRect(format) : safeAreaRect(format);
  const width = (box.width / 100) * container.width;
  const height = (box.height / 100) * container.height;
  const offsetX = (box.x / 100) * container.width;
  const offsetY = (box.y / 100) * container.height;
  return {
    x: place(container.x, container.width, width, offsetX, HORIZONTAL[box.anchor]),
    y: place(container.y, container.height, height, offsetY, VERTICAL[box.anchor]),
    width,
    height,
  };
}

export interface ImagePlacement {
  /** Beeldpositie en -grootte relatief aan de linkerbovenhoek van de laag. */
  x: number;
  y: number;
  width: number;
  height: number;
  /** Geplaatste pixels per bronpixel. Boven 1 wordt het beeld opgeschaald. */
  scale: number;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/**
 * Plaatst een bronbeeld in een rechthoek.
 * cover: vult de rechthoek en houdt het focuspunt zo dicht mogelijk bij het midden.
 * contain: past het beeld in de rechthoek en lijnt het uit volgens het focuspunt (0 = links/boven).
 */
export function placeImage(
  sourceWidth: number,
  sourceHeight: number,
  rect: Rect,
  fit: "cover" | "contain",
  focus: Point,
): ImagePlacement {
  const scaleX = rect.width / sourceWidth;
  const scaleY = rect.height / sourceHeight;
  const scale = fit === "cover" ? Math.max(scaleX, scaleY) : Math.min(scaleX, scaleY);
  const width = sourceWidth * scale;
  const height = sourceHeight * scale;

  if (fit === "contain") {
    return { x: (rect.width - width) * focus.x, y: (rect.height - height) * focus.y, width, height, scale };
  }

  return {
    x: clamp(rect.width / 2 - focus.x * width, rect.width - width, 0),
    y: clamp(rect.height / 2 - focus.y * height, rect.height - height, 0),
    width,
    height,
    scale,
  };
}

export function contains(outer: Rect, inner: Rect, tolerance = 0.5): boolean {
  return (
    inner.x >= outer.x - tolerance &&
    inner.y >= outer.y - tolerance &&
    inner.x + inner.width <= outer.x + outer.width + tolerance &&
    inner.y + inner.height <= outer.y + outer.height + tolerance
  );
}
