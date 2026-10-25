import type { ContentField, PostDocument } from "@flow/schema";
import { ImageIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "../components/ui/button";
import { Input, Label, Select, Textarea } from "../components/ui/input";
import type { Asset } from "../lib/types";
import { AssetPicker } from "./AssetPicker";

type Content = PostDocument["content"];

export function ContentForm({
  fields,
  content,
  assets,
  companyId,
  onChange,
  onAsset,
  layerTypes = {},
}: {
  /** Laagtype per veldsleutel, zodat een achtergrondveld ook merkachtergronden toont. */
  layerTypes?: Record<string, string>;
  fields: ContentField[];
  content: Content;
  assets: Record<string, Asset>;
  companyId: string;
  onChange: (key: string, value: Content[string]) => void;
  onAsset: (asset: Asset) => void;
}) {
  const [picking, setPicking] = useState<ContentField | null>(null);

  return (
    <div className="space-y-4">
      {fields.map((field) => {
        const value = content[field.key];
        const text = typeof value === "string" ? value : "";
        const counter = field.maxLength ? `${text.length}/${field.maxLength}` : null;
        return (
          <div key={field.key}>
            <div className="flex items-baseline justify-between">
              <Label htmlFor={field.key}>
                {field.label}
                {field.required && <span className="text-danger"> *</span>}
              </Label>
              {counter && <span className={`text-xs ${text.length > (field.maxLength ?? 0) ? "text-danger" : "text-muted"}`}>{counter}</span>}
            </div>
            {field.type === "text" && <Input id={field.key} value={text} maxLength={field.maxLength ?? undefined} onChange={(e) => onChange(field.key, e.target.value)} />}
            {field.type === "longtext" && <Textarea id={field.key} value={text} maxLength={field.maxLength ?? undefined} onChange={(e) => onChange(field.key, e.target.value)} />}
            {field.type === "date" && <Input id={field.key} type="date" value={text} onChange={(e) => onChange(field.key, e.target.value)} />}
            {field.type === "select" && (
              <Select id={field.key} value={text} onChange={(e) => onChange(field.key, e.target.value || null)}>
                <option value="">Geen</option>
                {field.options.map((option) => (
                  <option key={option}>{option}</option>
                ))}
              </Select>
            )}
            {field.type === "multiselect" && (
              <div className="flex flex-wrap gap-3">
                {field.options.map((option) => {
                  const list = Array.isArray(value) ? value : [];
                  const checked = list.includes(option);
                  return (
                    <label key={option} className="flex items-center gap-1.5 text-sm">
                      <input type="checkbox" checked={checked} onChange={() => onChange(field.key, checked ? list.filter((o) => o !== option) : [...list, option])} />
                      {option}
                    </label>
                  );
                })}
              </div>
            )}
            {field.type === "image" && (
              <div className="flex items-center gap-3">
                {text && assets[text] ? (
                  <img src={assets[text].url} alt="" className="h-14 w-24 rounded border border-border object-cover" />
                ) : (
                  <div className="flex h-14 w-24 items-center justify-center rounded border border-dashed border-border text-muted">
                    <ImageIcon size={18} />
                  </div>
                )}
                <div className="min-w-0 flex-1 text-xs text-muted">
                  {text && assets[text] ? `${assets[text].filename} · ${assets[text].width}x${assets[text].height}` : "Nog geen beeld"}
                </div>
                <Button variant="secondary" size="sm" onClick={() => setPicking(field)}>Kiezen</Button>
              </div>
            )}
            {field.help && <p className="mt-1 text-xs text-muted">{field.help}</p>}
          </div>
        );
      })}
      <AssetPicker
        companyId={companyId}
        kinds={picking && layerTypes[picking.key] === "background" ? ["background", "image"] : picking && layerTypes[picking.key] === "element" ? ["element"] : ["image"]}
        uploadKind={picking && layerTypes[picking.key] === "element" ? null : "image"}
        open={picking !== null}
        onOpenChange={(open) => !open && setPicking(null)}
        minWidth={picking?.minWidth ?? undefined}
        onPick={(asset) => {
          if (!picking) return;
          onAsset(asset);
          onChange(picking.key, asset.id);
          setPicking(null);
        }}
      />
    </div>
  );
}
