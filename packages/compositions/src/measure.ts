import type { TextMeasurer } from "@flow/layout";

let context: CanvasRenderingContext2D | null = null;

/** Meet tekst met de canvas-API van de browser, dus met precies de geladen fonts. */
export const canvasMeasure: TextMeasurer = (text, font, fontSize) => {
  if (!context) {
    context = document.createElement("canvas").getContext("2d");
  }
  if (!context) throw new Error("canvas 2d-context niet beschikbaar");
  context.font = `${font.weight} ${fontSize}px ${font.family}`;
  return context.measureText(text).width;
};
