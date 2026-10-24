import type { Format, Layer, LayerLayout } from "@flow/schema";

export interface ResolvedLayout {
  box: NonNullable<LayerLayout["box"]>;
  hidden: boolean;
  fit: "cover" | "contain";
  focus: { x: number; y: number };
  minFontSize: number;
  maxFontSize: number;
  maxLines: number;
  align: "left" | "center" | "right";
  verticalAlign: "top" | "center" | "bottom";
}

const DEFAULTS: Omit<ResolvedLayout, "box"> = {
  hidden: false,
  fit: "cover",
  focus: { x: 0.5, y: 0.5 },
  minFontSize: 24,
  maxFontSize: 72,
  maxLines: 3,
  align: "left",
  verticalAlign: "top",
};

function definedOnly(layout: LayerLayout | undefined): Partial<ResolvedLayout> {
  if (!layout) return {};
  return Object.fromEntries(
    Object.entries(layout).filter(([, value]) => value !== null && value !== undefined),
  ) as Partial<ResolvedLayout>;
}

export function formatKey(format: Format): string {
  return `${format.platform}/${format.id}`;
}

/** Voegt layouts samen in de volgorde default, layout_class, formaatsleutel. */
export function resolveLayout(layer: Layer, format: Format): ResolvedLayout {
  const merged = {
    ...DEFAULTS,
    ...definedOnly(layer.layouts["default"]),
    ...definedOnly(layer.layouts[format.layoutClass]),
    ...definedOnly(layer.layouts[formatKey(format)]),
  };
  if (!merged.box) {
    throw new Error(`laag ${layer.id} heeft geen box voor ${formatKey(format)}`);
  }
  return merged as ResolvedLayout;
}
