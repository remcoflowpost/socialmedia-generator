import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "../components/ui/button";
import { Badge, Card } from "../components/ui/card";
import { Dialog } from "../components/ui/dialog";
import { Input, Label, Select } from "../components/ui/input";
import { api } from "../lib/api";
import type { Asset, Company, User } from "../lib/types";

export function LibraryPage({ user }: { user: User }) {
  const queryClient = useQueryClient();
  const companies = useQuery({ queryKey: ["companies"], queryFn: () => api.get<Company[]>("/api/companies") });
  const [companyId, setCompanyId] = useState("");
  const [q, setQ] = useState("");
  const [origin, setOrigin] = useState("");
  const [kind, setKind] = useState("image");
  const [tags, setTags] = useState("");
  const [selected, setSelected] = useState<Asset | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!companyId && companies.data?.[0]) setCompanyId(companies.data[0].id);
  }, [companies.data, companyId]);

  const params = new URLSearchParams({ company_id: companyId });
  if (q) params.set("q", q);
  if (origin) params.set("origin", origin);
  if (kind) params.set("kind", kind);
  const assets = useQuery({ queryKey: ["assets", companyId, params.toString()], queryFn: () => api.get<Asset[]>(`/api/assets?${params}`), enabled: Boolean(companyId) });

  const upload = async (files: FileList) => {
    setError(null);
    for (const file of Array.from(files)) {
      const form = new FormData();
      form.append("company_id", companyId);
      form.append("file", file);
      form.append("kind", ["font", "logo", "background", "element"].includes(kind) ? kind : "image");
      form.append("tags", tags);
      try {
        await api.upload<Asset>("/api/assets", form);
      } catch (e) {
        setError(`${file.name}: ${(e as Error).message}`);
      }
    }
    await queryClient.invalidateQueries({ queryKey: ["assets", companyId] });
  };

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <div className="flex flex-wrap items-end gap-3">
        <h1 className="mr-auto text-xl font-semibold">Bibliotheek</h1>
        <Select className="w-56" value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
          {companies.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
        <Input className="w-56" placeholder="Zoeken op naam of tag" value={q} onChange={(e) => setQ(e.target.value)} />
        <Select className="w-40" value={origin} onChange={(e) => setOrigin(e.target.value)}>
          <option value="">Alle herkomst</option>
          <option value="upload">Upload</option>
          <option value="generated">Gegenereerd</option>
        </Select>
        <Select className="w-32" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="image">Beelden</option>
          <option value="logo">Logo's</option>
          <option value="font">Fonts</option>
          <option value="background">Achtergronden</option>
          <option value="element">Elementen</option>
          <option value="">Alles</option>
        </Select>
      </div>
      <Card className="flex flex-wrap items-end gap-3">
        <div className="min-w-60 flex-1">
          <Label>Tags voor nieuwe uploads (komma's)</Label>
          <Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="project-x, still" />
        </div>
        <input ref={fileInput} type="file" multiple className="hidden" onChange={(e) => e.target.files && upload(e.target.files)} />
        <Button onClick={() => fileInput.current?.click()} disabled={["logo", "font", "background", "element"].includes(kind) && user.role !== "admin"}>
          <Upload size={16} /> Uploaden
        </Button>
        {error && <p className="w-full text-sm text-danger">{error}</p>}
      </Card>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {assets.data?.map((asset) => (
          <button key={asset.id} className="text-left" onClick={() => setSelected(asset)}>
            {asset.kind === "font" ? (
              <div className="flex aspect-video items-center justify-center rounded border border-border bg-surface-2 text-2xl">Aa</div>
            ) : (
              <img src={asset.url} alt="" className="aspect-video w-full rounded border border-border bg-surface-2 object-contain" />
            )}
            <div className="mt-1 truncate text-sm">{asset.filename}</div>
            <div className="flex flex-wrap gap-1">
              <Badge tone={asset.origin === "generated" ? "warning" : "neutral"}>{asset.origin === "generated" ? "gegenereerd" : "upload"}</Badge>
              {asset.tags.map((tag) => <Badge key={tag}>{tag}</Badge>)}
            </div>
          </button>
        ))}
      </div>
      <Dialog open={selected !== null} onOpenChange={(open) => !open && setSelected(null)} title={selected?.filename ?? ""} wide>
        {selected && (
          <div className="grid gap-4 md:grid-cols-2">
            {selected.kind !== "font" && <img src={selected.url} alt="" className="w-full rounded border border-border" />}
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
              <dt className="text-muted">Afmetingen</dt><dd>{selected.width ? `${selected.width}x${selected.height}px` : "vector of font"}</dd>
              <dt className="text-muted">Type</dt><dd>{selected.mime}</dd>
              <dt className="text-muted">Origineel profiel</dt><dd>{selected.colorProfile ?? "geen (sRGB aangenomen)"}</dd>
              <dt className="text-muted">Herkomst</dt><dd>{selected.origin}</dd>
              <dt className="text-muted">Details</dt><dd><pre className="whitespace-pre-wrap text-xs">{JSON.stringify(selected.provenance, null, 2)}</pre></dd>
              <dt className="text-muted">Geupload</dt><dd>{new Date(selected.createdAt).toLocaleString("nl-NL")}</dd>
            </dl>
          </div>
        )}
      </Dialog>
    </div>
  );
}
