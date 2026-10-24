export interface FontSpec {
  /** CSS font-family, inclusief fallback. */
  family: string;
  weight: number;
  /** Extra ruimte per teken in em. */
  letterSpacing: number;
}

/** Meet de breedte in px van een tekst op een gegeven fontgrootte. */
export type TextMeasurer = (text: string, font: FontSpec, fontSize: number) => number;

export interface TextFitRequest {
  text: string;
  font: FontSpec;
  lineHeight: number;
  width: number;
  height: number;
  minFontSize: number;
  maxFontSize: number;
  maxLines: number;
}

export interface TextFitResult {
  fontSize: number;
  lines: string[];
  /** Breedte van de breedste regel in px. */
  textWidth: number;
  textHeight: number;
  overflow: boolean;
}

export function measureWithSpacing(measure: TextMeasurer, text: string, font: FontSpec, size: number): number {
  return measure(text, font, size) + font.letterSpacing * size * text.length;
}

/** Breekt tekst op woordgrenzen. Woorden die op zichzelf te breed zijn worden niet gesplitst. */
export function wrapText(text: string, font: FontSpec, fontSize: number, width: number, measure: TextMeasurer): string[] {
  const lines: string[] = [];
  for (const paragraph of text.split(/\r?\n/)) {
    const words = paragraph.split(/\s+/).filter(Boolean);
    let current = "";
    for (const word of words) {
      const candidate = current ? `${current} ${word}` : word;
      if (!current || measureWithSpacing(measure, candidate, font, fontSize) <= width) {
        current = candidate;
        continue;
      }
      lines.push(current);
      current = word;
    }
    lines.push(current);
  }
  return lines;
}

function evaluate(request: TextFitRequest, fontSize: number, measure: TextMeasurer): TextFitResult {
  const lines = wrapText(request.text, request.font, fontSize, request.width, measure);
  const textWidth = Math.max(0, ...lines.map((line) => measureWithSpacing(measure, line, request.font, fontSize)));
  const textHeight = lines.length * fontSize * request.lineHeight;
  const overflow =
    lines.length > request.maxLines || textHeight > request.height + 0.5 || textWidth > request.width + 0.5;
  return { fontSize, lines, textWidth, textHeight, overflow };
}

/**
 * Zoekt de grootste fontgrootte (hele px) tussen min en max waarop de tekst past.
 * Past de tekst ook op de minimale grootte niet, dan komt overflow terug in plaats van
 * stil afkappen; de aanroeper meldt dat als kwaliteitsfout.
 */
export function fitText(request: TextFitRequest, measure: TextMeasurer): TextFitResult {
  let low = Math.ceil(request.minFontSize);
  let high = Math.floor(request.maxFontSize);
  const smallest = evaluate(request, low, measure);
  if (smallest.overflow) return smallest;

  let best = smallest;
  while (low <= high) {
    const middle = Math.floor((low + high) / 2);
    const result = evaluate(request, middle, measure);
    if (result.overflow) {
      high = middle - 1;
      continue;
    }
    best = result;
    low = middle + 1;
  }
  return best;
}
