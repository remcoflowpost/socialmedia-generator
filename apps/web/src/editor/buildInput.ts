import type { Format, PostDocument, RenderAsset, RenderInput } from "@flow/schema";
import type { Asset, RenderContext } from "../lib/types";

export function toRenderAssets(assets: Record<string, Asset>): Record<string, RenderAsset> {
  return Object.fromEntries(
    Object.values(assets).map((a) => [a.id, { src: a.url, mime: a.mime, width: a.width, height: a.height }]),
  );
}

export function buildInput(
  context: RenderContext,
  document: PostDocument,
  assets: Record<string, Asset>,
  format: Format,
  showSafeZones: boolean,
): RenderInput {
  return {
    format,
    template: context.template,
    brand: context.brand,
    post: document,
    assets: toRenderAssets(assets),
    options: { showSafeZones, hideText: false },
  };
}
