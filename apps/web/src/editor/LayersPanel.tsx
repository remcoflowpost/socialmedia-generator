import type { BrandKitData, Layer, LayerOverride, PostDocument, TemplateDefinition } from "@flow/schema";
import { Eye, EyeOff, Lock, Sparkles } from "lucide-react";
import { useState } from "react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/card";
import type { Asset, User } from "../lib/types";
import { AssetPicker } from "./AssetPicker";

const TYPE_LABEL: Record<Layer["type"], string> = {
  background: "Achtergrond",
  image: "Beeld",
  element: "Element",
  logo: "Logo",
  text: "Tekst",
  shape: "Vorm",
  video: "Video",
};

const SOURCE_LABEL: Record<Layer["source"], string> = {
  upload: "upload",
  brand_asset: "merk-asset",
  generated: "gegenereerd",
  content_field: "contentveld",
  static: "vast",
};

function imageAssetId(layer: Layer, document: PostDocument): string | null {
  const override = document.overrides[layer.id]?.assetId;
  if (override) return override;
  const value = layer.field ? document.content[layer.field] : null;
  return typeof value === "string" ? value : null;
}

export function canEdit(layer: Layer, brand: BrandKitData, user: User): boolean {
  if (user.role === "admin") return true;
  if (!layer.editable) return false;
  return !(layer.type === "logo" && brand.locks.includes("logo"));
}

function FocusPicker({ asset, focus, onChange }: { asset: Asset; focus: { x: number; y: number }; onChange: (focus: { x: number; y: number }) => void }) {
  return (
    <div className="relative cursor-crosshair overflow-hidden rounded border border-border" title="Klik om het focuspunt te zetten">
      <img
        src={asset.url}
        alt=""
        className="block w-full"
        onClick={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          onChange({
            x: Math.round(((event.clientX - rect.left) / rect.width) * 100) / 100,
            y: Math.round(((event.clientY - rect.top) / rect.height) * 100) / 100,
          });
        }}
      />
      <span
        className="pointer-events-none absolute h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow"
        style={{ left: `${focus.x * 100}%`, top: `${focus.y * 100}%`, background: "rgba(232,179,63,0.8)" }}
      />
    </div>
  );
}

export function LayersPanel({
  template,
  brand,
  document,
  assets,
  companyId,
  user,
  onOverride,
  onAsset,
}: {
  template: TemplateDefinition;
  brand: BrandKitData;
  document: PostDocument;
  assets: Record<string, Asset>;
  companyId: string;
  user: User;
  onOverride: (layerId: string, override: LayerOverride | null) => void;
  onAsset: (asset: Asset) => void;
}) {
  const [replacing, setReplacing] = useState<string | null>(null);
  const layers = [...template.layers].sort((a, b) => b.z - a.z);

  return (
    <div className="space-y-2">
      {layers.map((layer) => {
        const editable = canEdit(layer, brand, user);
        const override = document.overrides[layer.id];
        const assetId = imageAssetId(layer, document);
        const asset = assetId ? assets[assetId] : undefined;
        const isImage = ["background", "image", "element"].includes(layer.type);
        const focus = override?.focus ?? layer.layouts["default"]?.focus ?? { x: 0.5, y: 0.5 };
        const patch = (changes: Partial<LayerOverride>) =>
          onOverride(layer.id, { assetId: null, focus: null, hidden: null, ...override, ...changes });

        return (
          <div key={layer.id} className="rounded-md border border-border bg-surface-2 p-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">{layer.id}</span>
              <Badge>{TYPE_LABEL[layer.type]}</Badge>
              <Badge>{SOURCE_LABEL[layer.source]}</Badge>
              <span className="ml-auto flex items-center gap-1">
                {!editable && <Lock size={14} className="text-muted" aria-label="Vergrendeld" />}
                {editable && (
                  <button
                    className="rounded p-1 text-muted hover:text-foreground"
                    onClick={() => patch({ hidden: override?.hidden ? null : true })}
                    aria-label={override?.hidden ? "Tonen" : "Verbergen"}
                  >
                    {override?.hidden ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                )}
              </span>
            </div>

            {layer.source === "generated" && (
              <p className="mt-2 flex items-center gap-1.5 text-xs text-muted">
                <Sparkles size={14} /> Generatie per laag volgt in fase 2.
              </p>
            )}

            {editable && isImage && asset && (
              <div className="mt-3 space-y-2">
                <FocusPicker asset={asset} focus={focus} onChange={(f) => patch({ focus: f })} />
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary" onClick={() => setReplacing(layer.id)}>Vervangen door upload</Button>
                  {(override?.focus || override?.assetId) && (
                    <Button size="sm" variant="ghost" onClick={() => onOverride(layer.id, null)}>Herstellen</Button>
                  )}
                </div>
                <p className="text-xs text-muted">Focuspunt: {Math.round(focus.x * 100)}%, {Math.round(focus.y * 100)}%. Geldt voor alle formaten.</p>
              </div>
            )}
          </div>
        );
      })}
      <AssetPicker
        companyId={companyId}
        open={replacing !== null}
        onOpenChange={(open) => !open && setReplacing(null)}
        onPick={(asset) => {
          if (!replacing) return;
          onAsset(asset);
          const current = document.overrides[replacing];
          onOverride(replacing, { focus: null, hidden: null, ...current, assetId: asset.id });
          setReplacing(null);
        }}
      />
    </div>
  );
}
