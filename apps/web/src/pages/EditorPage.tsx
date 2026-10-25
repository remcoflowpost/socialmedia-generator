import type { LayerOverride, LayoutReport, PostDocument } from "@flow/schema";
import * as Tabs from "@radix-ui/react-tabs";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, CalendarClock, Download, Save } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Badge, Card } from "../components/ui/card";
import { Input, Label, Switch } from "../components/ui/input";
import { buildInput } from "../editor/buildInput";
import { ContentForm } from "../editor/ContentForm";
import { ExportDialog } from "../editor/ExportDialog";
import { ScheduleDialog } from "../publishing/ScheduleDialog";
import { IssuesList } from "../editor/IssuesList";
import { LayersPanel } from "../editor/LayersPanel";
import { Preview } from "../editor/Preview";
import { api } from "../lib/api";
import { cn } from "../lib/cn";
import { formatKey, type Asset, type Company, type Post, type QualitySummary, type RenderContext, type User } from "../lib/types";

type SaveState = "opgeslagen" | "wijzigingen" | "opslaan" | "fout";
const STEPS = ["Bedrijf", "Template", "Content", "Lagen"] as const;

function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

export function EditorPage({ user }: { user: User }) {
  const { postId = "" } = useParams();
  const context = useQuery({ queryKey: ["render-context", postId], queryFn: () => api.get<RenderContext>(`/api/posts/${postId}/render-context`) });
  const companies = useQuery({ queryKey: ["companies"], queryFn: () => api.get<Company[]>("/api/companies") });
  const quality = useQuery({ queryKey: ["quality", postId], queryFn: () => api.get<QualitySummary>(`/api/posts/${postId}/quality`) });

  const [document, setDocument] = useState<PostDocument | null>(null);
  const [assets, setAssets] = useState<Record<string, Asset>>({});
  const [title, setTitle] = useState("");
  const [embargo, setEmbargo] = useState("");
  const [step, setStep] = useState<(typeof STEPS)[number]>("Content");
  const [activeFormat, setActiveFormat] = useState("");
  const [showSafeZones, setShowSafeZones] = useState(false);
  const [compare, setCompare] = useState(false);
  const [reports, setReports] = useState<Record<string, LayoutReport>>({});
  const [saveState, setSaveState] = useState<SaveState>("opgeslagen");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const dirty = useRef(false);
  const loadedFor = useRef<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    // Alleen bij de eerste load overnemen; latere refetches mogen lokale wijzigingen niet overschrijven.
    if (!context.data || loadedFor.current === postId) return;
    loadedFor.current = postId;
    setVersion(context.data.post.currentVersion);
    setDocument(context.data.post.document);
    setAssets(context.data.assets);
    setTitle(context.data.post.title);
    setEmbargo(toLocalInput(context.data.post.embargoUntil));
    setActiveFormat((current) => current || formatKey(context.data.formats[0]!));
  }, [context.data, postId]);

  const saveNow = useCallback(async (): Promise<boolean> => {
    if (!document) return false;
    setSaveState("opslaan");
    try {
      await api.put<Post>(`/api/posts/${postId}`, {
        document,
        title,
        ...(embargo ? { embargo_until: new Date(embargo).toISOString() } : { clear_embargo: true }),
      });
      dirty.current = false;
      setSaveState("opgeslagen");
      setSaveError(null);
      return true;
    } catch (e) {
      setSaveState("fout");
      setSaveError((e as Error).message);
      return false;
    }
  }, [document, title, embargo, postId]);

  // Autosave: overschrijft de werkkopie, maakt geen nieuwe versie.
  useEffect(() => {
    if (!dirty.current) return;
    setSaveState("wijzigingen");
    const timer = setTimeout(() => void saveNow(), 700);
    return () => clearTimeout(timer);
  }, [saveNow]);

  const update = (next: PostDocument) => {
    dirty.current = true;
    setDocument(next);
  };
  const addAsset = (asset: Asset) => setAssets((current) => ({ ...current, [asset.id]: asset }));
  const onReport = useCallback((report: LayoutReport) => {
    setReports((current) => (JSON.stringify(current[report.formatKey]) === JSON.stringify(report) ? current : { ...current, [report.formatKey]: report }));
  }, []);

  const formats = context.data?.formats ?? [];
  const format = formats.find((f) => formatKey(f) === activeFormat) ?? formats[0];
  const input = useMemo(
    () => (context.data && document && format ? buildInput(context.data, document, assets, format, showSafeZones) : null),
    [context.data, document, assets, format, showSafeZones],
  );

  if (context.error) return <div className="p-8 text-danger">{context.error.message}</div>;
  if (!context.data || !document || !input || !format) return <div className="p-8 text-muted">Laden...</div>;

  const ctx = context.data;
  const company = companies.data?.find((c) => c.id === ctx.post.companyId);
  const embargoActive = Boolean(embargo && new Date(embargo) > new Date());
  const currentIssues = reports[activeFormat]?.issues ?? [];
  const exportedReport = quality.data?.reports.find((r) => r.formatKey === activeFormat);
  const contrastIssues = exportedReport?.issues.filter((i) => i.code === "contrast_low") ?? [];

  const saveVersion = async () => {
    if (dirty.current && !(await saveNow())) return;
    const result = await api.post<{ number: number }>(`/api/posts/${postId}/versions`);
    setVersion(result.number);
    setSaveError(`Versie v${String(result.number).padStart(3, "0")} opgeslagen.`);
  };

  return (
    <div className="grid h-full grid-cols-[300px_1fr_340px]">
      {/* Stappenpaneel */}
      <aside className="flex min-h-0 flex-col border-r border-border">
        <div className="space-y-3 border-b border-border p-4">
          <Link to="/posts" className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground"><ArrowLeft size={14} /> Posts</Link>
          <Input value={title} onChange={(e) => { dirty.current = true; setTitle(e.target.value); }} aria-label="Werktitel" />
          <div className="flex items-center gap-2 text-xs text-muted">
            <span>v{String(version).padStart(3, "0")}</span>
            <span className={cn(saveState === "fout" && "text-danger")}>{saveState}</span>
          </div>
          {saveError && <p className={cn("text-xs", saveState === "fout" ? "text-danger" : "text-success")}>{saveError}</p>}
        </div>
        <nav className="flex border-b border-border">
          {STEPS.map((name) => (
            <button key={name} onClick={() => setStep(name)} className={cn("flex-1 py-2 text-xs", step === name ? "border-b-2 border-primary text-foreground" : "text-muted")}>
              {name}
            </button>
          ))}
        </nav>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {step === "Bedrijf" && (
            <div className="space-y-2 text-sm">
              <Label>Afzender</Label>
              <p className="font-medium">{company?.name}</p>
              <p className="text-muted">Bepaalt de brand kit: kleuren, fonts en logo. Klant, project of persoon vul je in bij Content.</p>
              <div className="flex gap-1 pt-2">
                {Object.entries(ctx.brand.colors).map(([name, color]) => (
                  <span key={name} title={name} className="h-6 w-6 rounded border border-border" style={{ background: color }} />
                ))}
              </div>
            </div>
          )}
          {step === "Template" && (
            <div className="space-y-2 text-sm">
              <Label>Template</Label>
              <p className="font-medium">{ctx.template.name}</p>
              <p className="text-muted">{ctx.template.description}</p>
            </div>
          )}
          {step === "Content" && (
            <div className="space-y-4">
              <ContentForm
                fields={ctx.template.fields}
                content={document.content}
                assets={assets}
                companyId={ctx.post.companyId}
                onAsset={addAsset}
                onChange={(key, value) => update({ ...document, content: { ...document.content, [key]: value } })}
              />
              <div>
                <Label htmlFor="embargo">Embargo tot</Label>
                <Input id="embargo" type="datetime-local" value={embargo} onChange={(e) => { dirty.current = true; setEmbargo(e.target.value); }} />
                {embargoActive && <p className="mt-1 text-xs text-warning">Embargo actief: exports krijgen EMBARGO_ in de bestandsnaam.</p>}
              </div>
            </div>
          )}
          {step === "Lagen" && (
            <LayersPanel
              template={ctx.template}
              brand={ctx.brand}
              document={document}
              assets={assets}
              companyId={ctx.post.companyId}
              user={user}
              onAsset={addAsset}
              onOverride={(layerId, override: LayerOverride | null) => {
                const overrides = { ...document.overrides };
                if (override) overrides[layerId] = override;
                else delete overrides[layerId];
                update({ ...document, overrides });
              }}
            />
          )}
        </div>
      </aside>

      {/* Preview */}
      <section className="flex min-h-0 flex-col">
        <div className="flex items-center gap-4 border-b border-border px-4 py-2">
          <Switch checked={showSafeZones} onChange={setShowSafeZones} label="Safe zones" />
          <Switch checked={compare} onChange={setCompare} label="Alle formaten" />
          <div className="ml-auto flex gap-2">
            <Button variant="secondary" size="sm" onClick={saveVersion}><Save size={14} /> Versie opslaan</Button>
            <Button size="sm" onClick={() => setExportOpen(true)}><Download size={14} /> Exporteren</Button>
            <Button size="sm" variant="secondary" onClick={() => setScheduleOpen(true)}><CalendarClock size={14} /> Inplannen</Button>
          </div>
        </div>
        {!compare && (
          <Tabs.Root value={activeFormat} onValueChange={setActiveFormat} className="flex min-h-0 flex-1 flex-col">
            <Tabs.List className="flex flex-wrap gap-1 border-b border-border px-4 py-2">
              {formats.map((f) => {
                const key = formatKey(f);
                const issues = reports[key]?.issues ?? [];
                const tone = issues.some((i) => i.severity === "error") ? "bg-danger" : issues.length ? "bg-warning" : null;
                return (
                  <Tabs.Trigger key={key} value={key} className="relative rounded px-2.5 py-1 text-xs text-muted data-[state=active]:bg-surface-2 data-[state=active]:text-foreground">
                    {f.label}
                    {tone && <span className={cn("absolute right-0.5 top-0.5 h-1.5 w-1.5 rounded-full", tone)} />}
                  </Tabs.Trigger>
                );
              })}
            </Tabs.List>
            <div className="min-h-0 flex-1 overflow-auto p-6">
              <Preview input={input} onReport={onReport} />
            </div>
          </Tabs.Root>
        )}
        {compare && (
          <div className="grid min-h-0 flex-1 grid-cols-2 gap-4 overflow-auto p-6 lg:grid-cols-4 xl:grid-cols-5">
            {formats.map((f) => (
              <button key={formatKey(f)} onClick={() => { setActiveFormat(formatKey(f)); setCompare(false); }} className="space-y-1 text-left">
                <Preview input={buildInput(ctx, document, assets, f, showSafeZones)} onReport={onReport} maxHeight="220px" />
                <div className="text-xs text-muted">{f.label}</div>
              </button>
            ))}
          </div>
        )}
      </section>

      {/* Meldingen */}
      <aside className="min-h-0 space-y-4 overflow-y-auto border-l border-border p-4">
        <Card className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="mb-0">Kwaliteit: {format.label}</Label>
            <span className="text-xs text-muted">{format.width}x{format.height}</span>
          </div>
          <IssuesList issues={currentIssues} />
        </Card>
        <Card className="space-y-2">
          <Label className="mb-0">Contrast (laatste export)</Label>
          {exportedReport ? (
            <IssuesList issues={contrastIssues} empty="Contrast in orde bij de laatste export." />
          ) : (
            <p className="text-sm text-muted">Contrast wordt gemeten op de echte pixels tijdens export.</p>
          )}
        </Card>
        {embargoActive && <Badge tone="warning">Embargo actief</Badge>}
        <p className="text-xs text-muted">Fouten blokkeren later de status "klaar voor publicatie", niet de handmatige download.</p>
      </aside>

      <ExportDialog
        open={exportOpen}
        onOpenChange={setExportOpen}
        postId={postId}
        formats={formats}
        liveReports={reports}
        embargoActive={embargoActive}
        beforeExport={async () => !dirty.current || (await saveNow())}
        onExported={(number) => setVersion(number)}
      />
      <ScheduleDialog open={scheduleOpen} onOpenChange={setScheduleOpen} postId={postId} />
    </div>
  );
}
