import type { BrandColors } from "@flow/schema";

const THEME_KEYS: Record<string, keyof BrandColors> = {
  primary: "primary",
  secondary: "secondary",
  accent: "accent",
  text_on_dark: "textOnDark",
  text_on_light: "textOnLight",
};

/** Zet een themasleutel (bijv. "primary") of #hex om naar #hex. Merkkleuren nooit hardcoded. */
export function resolveColor(value: string, colors: BrandColors): string {
  if (value.startsWith("#")) return value;
  const key = THEME_KEYS[value];
  if (!key) throw new Error(`onbekende themakleur: ${value}`);
  return colors[key];
}

export function hexToRgb(hex: string): [number, number, number] {
  const clean = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(clean.slice(i, i + 2), 16)) as [number, number, number];
}

function channel(value: number): number {
  const c = value / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

/** Relatieve luminantie volgens WCAG 2.x. */
export function relativeLuminance(r: number, g: number, b: number): number {
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

export function contrastRatio(luminanceA: number, luminanceB: number): number {
  const light = Math.max(luminanceA, luminanceB);
  const dark = Math.min(luminanceA, luminanceB);
  return (light + 0.05) / (dark + 0.05);
}

export function withOpacity(hex: string, opacity: number): string {
  const [r, g, b] = hexToRgb(hex);
  return `rgba(${r}, ${g}, ${b}, ${opacity})`;
}
