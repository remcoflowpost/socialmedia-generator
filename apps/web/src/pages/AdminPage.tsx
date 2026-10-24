import type { BrandKitData, TemplateDefinition } from "@flow/schema";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input, Label, Select } from "../components/ui/input";
import { api } from "../lib/api";
import type { Asset, Company } from "../lib/types";

const COLOR_LABELS: Record<keyof BrandKitData["colors"], string> = {
  primary: "Primair",
  secondary: "Secundair",
  accent: "Accent",
  textOnDark: "Tekst op donker",
  textOnLight: "Tekst op licht",
};
const LOCKS = [
  ["logo", "Logo"],
  ["colors", "Kleuren"],
  ["fonts", "Fonts"],
  ["style_anchor", "Stijlanker"],
] as const;

export function AdminPage() {
  const queryClient = useQueryClient();
  const companies = useQuery({ queryKey: ["companies"], queryFn: () => api.get<Company[]>("/api/companies") });
  const templates = useQuery({ queryKey: ["templates"], queryFn: () => api.get<TemplateDefinition[]>("/api/templates") });
  const [companyId, setCompanyId] = useState("");
  const kit = useQuery({
    queryKey: ["brand-kit", companyId],
    queryFn: () => api.get<{ data: BrandKitData; version: number }>(`/api/companies/${companyId}/brand-kit`),
    enabled: Boolean(companyId),
  });
  const brandAssets = useQuery({
    queryKey: ["assets", companyId, "brand"],
    queryFn: () => api.get<Asset[]>(`/api/assets?company_id=${companyId}`),
    enabled: Boolean(companyId),
  });
  const [draft, setDraft] = useState<BrandKitData | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId && companies.data?.[0]) setCompanyId(companies.data[0].id);
  }, [companies.data, companyId]);
  useEffect(() => setDraft(kit.data?.data ?? null), [kit.data]);

  const logos = brandAssets.data?.filter((a) => a.kind === "logo") ?? [];
  const fonts = brandAssets.data?.filter((a) => a.kind === "font") ?? [];

  const save = async () => {
    if (!draft) return;
    try {
      const saved = await api.put<{ version: number }>(`/api/companies/${companyId}/brand-kit`, draft);
      setMessage(`Brand kit opgeslagen (versie ${saved.version}).`);
      await queryClient.invalidateQueries({ queryKey: ["brand-kit", companyId] });
    } catch (e) {
      setMessage((e as Error).message);
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <div className="flex items-center gap-3">
        <h1 className="mr-auto text-xl font-semibold">Beheer</h1>
        <Select className="w-64" value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
          {companies.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
      </div>

      {draft && (
        <Card className="space-y-6">
          <h2 className="font-semibold">Brand kit</h2>
          <section>
            <Label>Kleuren</Label>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
              {(Object.keys(COLOR_LABELS) as (keyof BrandKitData["colors"])[]).map((key) => (
                <div key={key} className="space-y-1">
                  <div className="text-xs text-muted">{COLOR_LABELS[key]}</div>
                  <div className="flex gap-2">
                    <input type="color" value={draft.colors[key]} onChange={(e) => setDraft({ ...draft, colors: { ...draft.colors, [key]: e.target.value } })} className="h-10 w-10 rounded border border-border bg-transparent" />
                    <Input value={draft.colors[key]} onChange={(e) => setDraft({ ...draft, colors: { ...draft.colors, [key]: e.target.value } })} />
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="grid gap-4 md:grid-cols-2">
            {(["heading", "body"] as const).map((role) => {
              const font = draft.fonts[role];
              return (
                <div key={role} className="space-y-2">
                  <Label>{role === "heading" ? "Font koppen" : "Font lopende tekst"}</Label>
                  <Input value={font.family} onChange={(e) => setDraft({ ...draft, fonts: { ...draft.fonts, [role]: { ...font, family: e.target.value } } })} placeholder="Familienaam" />
                  <Select
                    value={font.files[0]?.assetId ?? ""}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        fonts: { ...draft.fonts, [role]: { ...font, files: e.target.value ? [{ assetId: e.target.value, weight: font.files[0]?.weight ?? 400, style: "normal" }] : [] } },
                      })
                    }
                  >
                    <option value="">Geen bestand (alleen fallback)</option>
                    {fonts.map((f) => <option key={f.id} value={f.id}>{f.filename}</option>)}
                  </Select>
                  <Input value={font.fallback} onChange={(e) => setDraft({ ...draft, fonts: { ...draft.fonts, [role]: { ...font, fallback: e.target.value } } })} placeholder="Fallback, bijv. Arial, sans-serif" />
                </div>
              );
            })}
          </section>

          <section className="grid gap-4 md:grid-cols-3">
            {(["logoLight", "logoDark", "logoIcon"] as const).map((key) => (
              <div key={key}>
                <Label>{{ logoLight: "Logo licht (op donker)", logoDark: "Logo donker (op licht)", logoIcon: "Icoon" }[key]}</Label>
                <Select value={draft.logos[key] ?? ""} onChange={(e) => setDraft({ ...draft, logos: { ...draft.logos, [key]: e.target.value || null } })}>
                  <option value="">Geen</option>
                  {logos.map((l) => <option key={l.id} value={l.id}>{l.filename}</option>)}
                </Select>
              </div>
            ))}
          </section>
          <p className="text-xs text-muted">Logo's en fonts upload je in de Bibliotheek (soort "Logo's" of "Fonts").</p>

          <section>
            <Label>Locks voor editors</Label>
            <div className="flex flex-wrap gap-4 text-sm">
              {LOCKS.map(([key, label]) => (
                <label key={key} className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={draft.locks.includes(key)}
                    onChange={(e) => setDraft({ ...draft, locks: e.target.checked ? [...draft.locks, key] : draft.locks.filter((l) => l !== key) })}
                  />
                  {label}
                </label>
              ))}
            </div>
          </section>

          <section>
            <Label>Stijlanker (voor generatie in fase 2)</Label>
            <Input value={draft.styleAnchor.description} onChange={(e) => setDraft({ ...draft, styleAnchor: { ...draft.styleAnchor, description: e.target.value } })} />
          </section>

          <div className="flex items-center gap-3">
            <Button onClick={save}>Opslaan</Button>
            {message && <span className="text-sm text-muted">{message}</span>}
          </div>
        </Card>
      )}

      <Card className="space-y-2">
        <h2 className="font-semibold">Templates</h2>
        <p className="text-sm text-muted">Templates staan als YAML in de repo (map templates/) en worden geladen met het seed-script.</p>
        <ul className="text-sm">
          {templates.data?.map((t) => (
            <li key={t.key}>{t.name} <span className="text-muted">({t.key}, v{t.version}, {t.layers.length} lagen)</span></li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
