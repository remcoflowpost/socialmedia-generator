import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { useRef, useState } from "react";
import { Button } from "../components/ui/button";
import { Dialog } from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { api } from "../lib/api";
import type { Asset } from "../lib/types";

export function AssetPicker({
  companyId,
  open,
  onOpenChange,
  onPick,
  minWidth,
  kinds = ["image"],
  uploadKind = "image",
}: {
  companyId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPick: (asset: Asset) => void;
  minWidth?: number;
  /** Welke soorten uit de bibliotheek te tonen, bijv. ["background", "image"]. */
  kinds?: string[];
  /** Soort voor een nieuwe upload; null = uploaden niet aanbieden (merkmateriaal, alleen via Bibliotheek). */
  uploadKind?: string | null;
}) {
  const queryClient = useQueryClient();
  const [q, setQ] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const assets = useQuery({
    queryKey: ["assets", companyId, kinds.join(","), q],
    queryFn: () =>
      api.get<Asset[]>(
        `/api/assets?company_id=${companyId}${kinds.map((k) => `&kind=${k}`).join("")}${q ? `&q=${encodeURIComponent(q)}` : ""}`,
      ),
    enabled: open,
  });

  const upload = async (file: File) => {
    setUploading(true);
    setError(null);
    const form = new FormData();
    form.append("company_id", companyId);
    form.append("file", file);
    form.append("kind", uploadKind ?? "image");
    try {
      const asset = await api.upload<Asset>("/api/assets", form);
      await queryClient.invalidateQueries({ queryKey: ["assets", companyId] });
      onPick(asset);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Beeld kiezen" wide>
      <div className="mb-4 flex gap-2">
        <Input placeholder="Zoek op bestandsnaam of tag" value={q} onChange={(e) => setQ(e.target.value)} />
        {uploadKind && (
          <>
            <input ref={fileInput} type="file" accept="image/*,.heic" className="hidden" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
            <Button variant="secondary" onClick={() => fileInput.current?.click()} disabled={uploading}>
              <Upload size={16} /> {uploading ? "Uploaden..." : "Uploaden"}
            </Button>
          </>
        )}
      </div>
      {!uploadKind && <p className="mb-3 text-xs text-muted">Merkmateriaal van dit bedrijf. Nieuwe achtergronden en elementen voegt een admin toe in de Bibliotheek.</p>}
      {assets.data?.length === 0 && <p className="mb-3 text-sm text-muted">Nog niets in deze categorie.</p>}
      {error && <p className="mb-3 text-sm text-danger">{error}</p>}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {assets.data?.map((asset) => {
          const small = minWidth && asset.width && asset.width < minWidth;
          return (
            <button key={asset.id} onClick={() => onPick(asset)} className="group text-left">
              <img src={asset.url} alt="" className="aspect-video w-full rounded border border-border object-cover group-hover:border-primary" />
              <div className="mt-1 truncate text-xs">{asset.filename}</div>
              <div className={`text-xs ${small ? "text-warning" : "text-muted"}`}>
                {asset.width}x{asset.height} {asset.origin === "generated" ? "· gegenereerd" : ""}
              </div>
            </button>
          );
        })}
      </div>
    </Dialog>
  );
}
