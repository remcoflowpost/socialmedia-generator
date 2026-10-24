import { contrastRatio, hexToRgb, relativeLuminance } from "@flow/layout";
import type { LayoutReport, QualityIssue } from "@flow/schema";

export interface RawImage {
  data: Uint8Array | Buffer;
  width: number;
  height: number;
  channels: number;
}

/** WCAG AA: 4,5:1 voor normale tekst, 3:1 voor grote tekst. */
export const CONTRAST_NORMAL = 4.5;
export const CONTRAST_LARGE = 3;
/**
 * WCAG noemt 24 CSS-px groot, maar een post van 1080 px wordt op een telefoon ongeveer op
 * een derde getoond. Daarom: groot vanaf 3,5% van de canvasbreedte (ca. 38 px op 1080).
 */
export const LARGE_TEXT_RATIO = 0.035;

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  const index = Math.min(sorted.length - 1, Math.max(0, Math.round((sorted.length - 1) * p)));
  return sorted[index]!;
}

/**
 * Luminanties van de achtergrond onder een tekstbox, uit een render zonder tekstlagen.
 * Bemonstert maximaal ongeveer 20.000 pixels per box.
 */
export function sampleLuminance(image: RawImage, box: { x: number; y: number; width: number; height: number }): number[] {
  const x0 = Math.max(0, Math.floor(box.x));
  const y0 = Math.max(0, Math.floor(box.y));
  const x1 = Math.min(image.width, Math.ceil(box.x + box.width));
  const y1 = Math.min(image.height, Math.ceil(box.y + box.height));
  const area = Math.max(1, (x1 - x0) * (y1 - y0));
  const step = Math.max(1, Math.floor(Math.sqrt(area / 20_000)));
  const values: number[] = [];
  for (let y = y0; y < y1; y += step) {
    for (let x = x0; x < x1; x += step) {
      const i = (y * image.width + x) * image.channels;
      values.push(relativeLuminance(image.data[i]!, image.data[i + 1]!, image.data[i + 2]!));
    }
  }
  return values.sort((a, b) => a - b);
}

/**
 * Contrastcheck per tekstlaag. Achtergrond onder tekst is zelden egaal, dus we nemen het
 * slechtste van de 10e en 90e percentiel. Dat is een heuristiek, daarom een waarschuwing.
 */
export function contrastIssues(report: LayoutReport, background: RawImage): QualityIssue[] {
  const issues: QualityIssue[] = [];
  for (const layer of report.layers) {
    if (layer.type !== "text" || layer.hidden || !layer.color || !layer.fontSize) continue;
    const samples = sampleLuminance(background, layer.box);
    if (samples.length === 0) continue;
    const textLuminance = relativeLuminance(...hexToRgb(layer.color));
    const ratio = Math.min(
      contrastRatio(textLuminance, percentile(samples, 0.1)),
      contrastRatio(textLuminance, percentile(samples, 0.9)),
    );
    const large = layer.fontSize >= report.width * LARGE_TEXT_RATIO;
    const threshold = large ? CONTRAST_LARGE : CONTRAST_NORMAL;
    if (ratio >= threshold) continue;
    issues.push({
      code: "contrast_low",
      severity: "warning",
      message: `Contrast van "${layer.id}" is ${ratio.toFixed(1)}:1, richtlijn is ${threshold}:1.`,
      layerId: layer.id,
      formatKey: report.formatKey,
      details: { ratio: Number(ratio.toFixed(2)), threshold },
    });
  }
  return issues;
}
