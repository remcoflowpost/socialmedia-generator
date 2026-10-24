import type {
  BrandKitData,
  Layer,
  LayerReport,
  LayoutReport,
  QualityIssue,
  RenderInput,
} from "@flow/schema";
import { resolveColor, withOpacity } from "./color";
import { boxToRect, contains, placeImage, safeAreaRect, type ImagePlacement, type Rect } from "./geometry";
import { formatKey, resolveLayout } from "./resolve";
import { fitText, type FontSpec, type TextMeasurer } from "./text";

/** Onder deze verhouding (bronpixels per geplaatste pixel) een waarschuwing, daaronder een fout. */
export const RESOLUTION_WARNING = 1;
export const RESOLUTION_ERROR = 0.75;

interface BaseLayer {
  id: string;
  type: Layer["type"];
  z: number;
  rect: Rect;
}

export interface ComputedImageLayer extends BaseLayer {
  kind: "image";
  src: string | null;
  placement: ImagePlacement | null;
  placeholder: string | null;
}

export interface ComputedTextLayer extends BaseLayer {
  kind: "text";
  lines: string[];
  fontSize: number;
  lineHeight: number;
  color: string;
  font: FontSpec;
  uppercase: boolean;
  align: "left" | "center" | "right";
  textRect: Rect;
  overflow: boolean;
}

export interface ComputedShapeLayer extends BaseLayer {
  kind: "shape";
  background: string;
  opacity: number;
  radius: number;
}

export type ComputedLayer = ComputedImageLayer | ComputedTextLayer | ComputedShapeLayer;

export interface ComputedFrame {
  width: number;
  height: number;
  safeArea: Rect;
  layers: ComputedLayer[];
  report: LayoutReport;
}

export type FontRole = "heading" | "body";

export function fontFaceName(role: FontRole): string {
  return `flow-${role}`;
}

/** CSS font-family voor een merkfont. Zonder fontbestanden alleen de fallback. */
export function fontFamilyCss(brand: BrandKitData, role: FontRole): string {
  const font = brand.fonts[role];
  if (font.files.length === 0) return font.fallback;
  return `"${fontFaceName(role)}", ${font.fallback}`;
}

function contentText(input: RenderInput, field: string): string {
  const value = input.post.content[field];
  if (Array.isArray(value)) return value.join(", ");
  return (value ?? "").trim();
}

function isEmpty(value: RenderInput["post"]["content"][string] | undefined): boolean {
  if (Array.isArray(value)) return value.length === 0;
  return !value || !value.trim();
}

function imageAssetId(input: RenderInput, layer: Layer): string | null {
  const override = input.post.overrides[layer.id];
  if (override?.assetId) return override.assetId;
  if (layer.source === "brand_asset" && layer.brandAsset) {
    const logos = input.brand.logos;
    const key = { logo_light: "logoLight", logo_dark: "logoDark", logo_icon: "logoIcon" } as const;
    return logos[key[layer.brandAsset]] ?? null;
  }
  if (layer.field) {
    const value = input.post.content[layer.field];
    return typeof value === "string" && value ? value : null;
  }
  return null;
}

function shapeBackground(layer: Layer, brand: BrandKitData): string {
  const style = layer.shapeStyle;
  if (!style) return "transparent";
  if (style.gradient) {
    const g = style.gradient;
    const from = withOpacity(resolveColor(g.fromColor, brand.colors), g.fromOpacity);
    const to = withOpacity(resolveColor(g.toColor, brand.colors), g.toOpacity);
    return `linear-gradient(${g.angle}deg, ${from}, ${to})`;
  }
  return style.fill ? resolveColor(style.fill, brand.colors) : "transparent";
}

function hiddenReport(layer: Layer): LayerReport {
  return {
    id: layer.id,
    type: layer.type,
    hidden: true,
    box: { x: 0, y: 0, width: 0, height: 0 },
    fontSize: null,
    lines: null,
    color: null,
    sourceScale: null,
  };
}

/**
 * Berekent de volledige layout van een formaat: posities, tekst-fit, beeldplaatsing en
 * de kwaliteitschecks die zonder pixels kunnen (alles behalve contrast).
 * Puur: dezelfde invoer en dezelfde meter geven dezelfde uitkomst in browser en render-service.
 */
export function computeLayout(input: RenderInput, measure: TextMeasurer): ComputedFrame {
  const { format, template, brand } = input;
  const key = formatKey(format);
  const safeArea = safeAreaRect(format);
  const issues: QualityIssue[] = [];
  const reports: LayerReport[] = [];
  const layers: ComputedLayer[] = [];

  const issue = (entry: Omit<QualityIssue, "formatKey" | "details"> & { details?: QualityIssue["details"] }) =>
    issues.push({ details: {}, ...entry, formatKey: key });

  for (const field of template.fields) {
    if (!field.required || !isEmpty(input.post.content[field.key])) continue;
    issue({ code: "missing_required_field", severity: "error", layerId: null, message: `Veld "${field.label}" is verplicht.` });
  }
  for (const role of ["heading", "body"] as const) {
    if (brand.fonts[role].files.length > 0) continue;
    issue({
      code: "font_missing",
      severity: "warning",
      layerId: null,
      message: `Brand kit heeft geen fontbestand voor ${role === "heading" ? "koppen" : "lopende tekst"}, fallback wordt gebruikt.`,
    });
  }

  const ordered = [...template.layers].sort((a, b) => a.z - b.z);
  for (const layer of ordered) {
    const layout = resolveLayout(layer, format);
    const override = input.post.overrides[layer.id];
    const hidden = override?.hidden ?? layout.hidden;
    if (hidden) {
      reports.push(hiddenReport(layer));
      continue;
    }

    const rect = boxToRect(layout.box, format);
    const base = { id: layer.id, type: layer.type, z: layer.z, rect };

    if (layer.type === "shape") {
      const style = layer.shapeStyle;
      layers.push({ ...base, kind: "shape", background: shapeBackground(layer, brand), opacity: style?.opacity ?? 1, radius: style?.radius ?? 0 });
      reports.push({ ...hiddenReport(layer), hidden: false, box: rect });
      continue;
    }

    if (layer.type === "text") {
      const text = layer.field ? contentText(input, layer.field) : (layer.static ?? "");
      if (!text) {
        reports.push(hiddenReport(layer));
        continue;
      }
      const style = layer.textStyle!;
      const font: FontSpec = { family: fontFamilyCss(brand, style.font), weight: style.weight, letterSpacing: style.letterSpacing };
      const shown = style.uppercase ? text.toLocaleUpperCase("nl-NL") : text;
      const fit = fitText(
        {
          text: shown,
          font,
          lineHeight: style.lineHeight,
          width: rect.width,
          height: rect.height,
          minFontSize: layout.minFontSize,
          maxFontSize: layout.maxFontSize,
          maxLines: layout.maxLines,
        },
        measure,
      );
      const offsetX = { left: 0, center: (rect.width - fit.textWidth) / 2, right: rect.width - fit.textWidth }[layout.align];
      const offsetY = { top: 0, center: (rect.height - fit.textHeight) / 2, bottom: rect.height - fit.textHeight }[layout.verticalAlign];
      const textRect = { x: rect.x + offsetX, y: rect.y + offsetY, width: fit.textWidth, height: fit.textHeight };
      const color = resolveColor(style.color, brand.colors);

      layers.push({
        ...base,
        kind: "text",
        lines: fit.lines,
        fontSize: fit.fontSize,
        lineHeight: style.lineHeight,
        color,
        font,
        uppercase: style.uppercase,
        align: layout.align,
        textRect,
        overflow: fit.overflow,
      });
      reports.push({ id: layer.id, type: layer.type, hidden: false, box: textRect, fontSize: fit.fontSize, lines: fit.lines, color, sourceScale: null });

      if (fit.overflow) {
        issue({
          code: "text_overflow",
          severity: "error",
          layerId: layer.id,
          message: `Tekst in "${layer.id}" past niet, ook niet op ${fit.fontSize}px. Maak de tekst korter.`,
          details: { lines: fit.lines.length, maxLines: layout.maxLines },
        });
      }
      if (!contains(safeArea, textRect)) {
        issue({ code: "outside_safe_zone", severity: "error", layerId: layer.id, message: `Tekst in "${layer.id}" valt (deels) buiten de safe zone.` });
      }
      continue;
    }

    // Beeldlagen: background, image, element, logo. Video volgt in fase 3.
    const assetId = imageAssetId(input, layer);
    const asset = assetId ? input.assets[assetId] : undefined;
    if (!asset) {
      const label = layer.type === "logo" ? "Logo ontbreekt in de brand kit" : "Beeld ontbreekt";
      layers.push({ ...base, kind: "image", src: null, placement: null, placeholder: label });
      reports.push({ ...hiddenReport(layer), hidden: false, box: rect });
      if (assetId || layer.type === "logo") {
        issue({ code: "missing_asset", severity: "error", layerId: layer.id, message: `${label} (${layer.id}).` });
      }
      continue;
    }

    const sourceWidth = asset.width ?? rect.width;
    const sourceHeight = asset.height ?? rect.height;
    const focus = override?.focus ?? layout.focus;
    const placement = placeImage(sourceWidth, sourceHeight, rect, layout.fit, focus);
    const visible: Rect = {
      x: rect.x + Math.max(placement.x, 0),
      y: rect.y + Math.max(placement.y, 0),
      width: Math.min(placement.width, rect.width),
      height: Math.min(placement.height, rect.height),
    };
    layers.push({ ...base, kind: "image", src: asset.src, placement, placeholder: null });
    reports.push({ id: layer.id, type: layer.type, hidden: false, box: visible, fontSize: null, lines: null, color: null, sourceScale: placement.scale });

    const isVector = asset.mime === "image/svg+xml";
    const ratio = 1 / placement.scale;
    if (!isVector && ratio < RESOLUTION_ERROR) {
      issue({
        code: "resolution_too_low",
        severity: "error",
        layerId: layer.id,
        message: `Beeld in "${layer.id}" is te klein: ${sourceWidth}x${sourceHeight}px wordt ${Math.round(placement.width)}x${Math.round(placement.height)}px.`,
        details: { ratio: Number(ratio.toFixed(3)) },
      });
    } else if (!isVector && ratio < RESOLUTION_WARNING) {
      issue({
        code: "resolution_low",
        severity: "warning",
        layerId: layer.id,
        message: `Beeld in "${layer.id}" wordt opgeschaald (${Math.round(ratio * 100)}% van de benodigde resolutie).`,
        details: { ratio: Number(ratio.toFixed(3)) },
      });
    }
    if (layer.type === "logo" && !contains(safeArea, visible)) {
      issue({ code: "outside_safe_zone", severity: "error", layerId: layer.id, message: "Logo valt (deels) buiten de safe zone." });
    }
  }

  return {
    width: format.width,
    height: format.height,
    safeArea,
    layers,
    report: { formatKey: key, width: format.width, height: format.height, layers: reports, issues },
  };
}
