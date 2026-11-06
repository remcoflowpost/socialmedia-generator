import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, Film, Send, Upload } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Badge, Card } from "../components/ui/card";
import { Input, Label, Select, Textarea } from "../components/ui/input";
import { api } from "../lib/api";
import { cn } from "../lib/cn";
import type { Asset, Channel, ChannelList, Company, Job, Post, PublishJob, PublishMode } from "../lib/types";

/** Een te publiceren bestand: uit de bibliotheek of uit een afgeronde export. */
interface Media {
  id: string;
  label: string;
  url: string;
  video: boolean;
  formatKey?: string;
  ref: { asset_id: string } | { export_job_id: string; file: string };
}

const CAPTION_LIMITS: Record<string, number> = { x: 280, bluesky: 300, threads: 500, instagram: 2200, facebook: 63206, linkedin: 3000 };
const platformOf = (channel: Channel) => channel.platform.split("-")[0] ?? channel.platform;

const fromAsset = (asset: Asset): Media => ({
  id: `asset:${asset.id}`,
  label: asset.filename,
  url: asset.url,
  video: asset.kind === "video",
  ref: { asset_id: asset.id },
});

/** Standaardkeuze per kanaal: bij exportbestanden het formaat van dat platform (feed voor
 *  story), anders alle gekozen bestanden. */
function defaultMedia(channel: Channel, media: Media[]): string[] {
  const exported = media.filter((m) => m.formatKey);
  if (exported.length === 0) return media.map((m) => m.id);
  const own = exported.filter((m) => m.formatKey!.startsWith(`${platformOf(channel)}/`));
  const feed = own.filter((m) => !m.formatKey!.endsWith("/story"));
  const pick = feed[0] ?? own[0] ?? exported[0];
  return pick ? [pick.id] : [];
}

const STATUS: Record<string, string> = { queued: "In de wachtrij", running: "Bezig", done: "Verstuurd", failed: "Mislukt" };
const MODE: Record<PublishMode, string> = { now: "Direct", schedule: "Ingepland", draft: "Concept" };

export function PublishPage() {
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  const exportJobId = params.get("job");
  const postId = params.get("post");

  const companies = useQuery({ queryKey: ["companies"], queryFn: () => api.get<Company[]>("/api/companies") });
  const post = useQuery({ queryKey: ["post", postId], queryFn: () => api.get<Post>(`/api/posts/${postId}`), enabled: Boolean(postId) });
  const exportJob = useQuery({ queryKey: ["job", exportJobId], queryFn: () => api.get<Job>(`/api/jobs/${exportJobId}`), enabled: Boolean(exportJobId) });

  const [companyId, setCompanyId] = useState("");
  const [media, setMedia] = useState<Media[]>([]);
  const [channelIds, setChannelIds] = useState<string[]>([]);
  const [overrides, setOverrides] = useState<Record<string, string[]>>({});
  const [caption, setCaption] = useState("");
  const [mode, setMode] = useState<PublishMode>("now");
  const [scheduledAt, setScheduledAt] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (post.data) setCompanyId(post.data.companyId);
    else if (!postId && !companyId && companies.data?.[0]) setCompanyId(companies.data[0].id);
  }, [companies.data, companyId, post.data, postId]);

  // Exportbestanden klaarzetten als we vanuit de exportdialoog komen.
  useEffect(() => {
    const result = exportJob.data?.result;
    if (!result || !exportJobId) return;
    setMedia(
      result.files
        .filter((f) => f.severity !== "error")
        .map((f) => ({
          id: `export:${f.name}`,
          label: f.name,
          url: `/api/jobs/${exportJobId}/download?file=${encodeURIComponent(f.name)}`,
          video: f.name.endsWith(".mp4"),
          formatKey: f.formatKey,
          ref: { export_job_id: exportJobId, file: f.name },
        })),
    );
  }, [exportJob.data, exportJobId]);

  const channels = useQuery({
    queryKey: ["publish-channels", companyId],
    queryFn: () => api.get<ChannelList>(`/api/publish/channels?company_id=${companyId}`),
    enabled: Boolean(companyId),
  });
  const library = useQuery({
    queryKey: ["assets", companyId, "publish"],
    queryFn: async () => {
      const [images, videos] = await Promise.all([
        api.get<Asset[]>(`/api/assets?company_id=${companyId}&kind=image`),
        api.get<Asset[]>(`/api/assets?company_id=${companyId}&kind=video`),
      ]);
      return [...videos, ...images].sort((a, b) => b.createdAt.localeCompare(a.createdAt)).slice(0, 30);
    },
    enabled: Boolean(companyId),
  });
  const history = useQuery({
    queryKey: ["publish-history", companyId],
    queryFn: () => api.get<PublishJob[]>(`/api/publish/history?company_id=${companyId}`),
    enabled: Boolean(companyId),
    refetchInterval: (query) => (query.state.data?.some((j) => ["queued", "running"].includes(j.status)) ? 1500 : false),
  });
  const current = history.data?.find((j) => j.id === jobId);

  const changeCompany = (id: string) => {
    setCompanyId(id);
    setChannelIds([]);
    setOverrides({});
    setMedia((list) => list.filter((m) => !("asset_id" in m.ref)));
  };

  const toggleMedia = (item: Media) =>
    setMedia((list) => (list.some((m) => m.id === item.id) ? list.filter((m) => m.id !== item.id) : [...list, item]));

  const upload = async (files: FileList) => {
    setError(null);
    for (const file of Array.from(files)) {
      const form = new FormData();
      form.append("company_id", companyId);
      form.append("file", file);
      form.append("kind", file.type.startsWith("video/") ? "video" : "image");
      try {
        const asset = await api.upload<Asset>("/api/assets", form);
        setMedia((list) => [...list, fromAsset(asset)]);
      } catch (e) {
        setError(`${file.name}: ${(e as Error).message}`);
      }
    }
    await queryClient.invalidateQueries({ queryKey: ["assets", companyId] });
  };

  const selectedChannels = useMemo(
    () => (channels.data?.channels ?? []).filter((c) => channelIds.includes(c.id)),
    [channels.data, channelIds],
  );
  const mediaFor = (channel: Channel) =>
    (overrides[channel.id] ?? defaultMedia(channel, media)).filter((id) => media.some((m) => m.id === id));
  const toggleChannelMedia = (channel: Channel, id: string) => {
    const now = mediaFor(channel);
    setOverrides({ ...overrides, [channel.id]: now.includes(id) ? now.filter((x) => x !== id) : [...now, id] });
  };

  const limit = Math.min(...selectedChannels.map((c) => CAPTION_LIMITS[platformOf(c)] ?? Infinity));
  const tooLong = Number.isFinite(limit) && caption.length > limit;
  const embargo = post.data?.embargoUntil && new Date(post.data.embargoUntil) > new Date() ? new Date(post.data.embargoUntil) : null;
  const busy = current ? ["queued", "running"].includes(current.status) : false;
  const canSubmit =
    selectedChannels.length > 0 &&
    !busy &&
    !tooLong &&
    (mode !== "schedule" || scheduledAt !== "") &&
    selectedChannels.every((c) => mediaFor(c).length > 0 || caption.trim() !== "");

  const submit = async () => {
    setError(null);
    try {
      const job = await api.post<Job>("/api/publish", {
        company_id: companyId,
        caption,
        mode,
        scheduled_at: mode === "schedule" ? new Date(scheduledAt).toISOString() : null,
        channels: selectedChannels.map((channel) => ({
          channel_id: channel.id,
          media: mediaFor(channel).map((id) => media.find((m) => m.id === id)!.ref),
        })),
      });
      setJobId(job.id);
      await queryClient.invalidateQueries({ queryKey: ["publish-history", companyId] });
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const thumb = (item: Media, className?: string) =>
    item.video ? (
      <div className={cn("flex items-center justify-center bg-surface-2 text-muted", className)}><Film size={20} /></div>
    ) : (
      <img src={item.url} alt="" className={cn("bg-surface-2 object-cover", className)} />
    );

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <div className="flex flex-wrap items-end gap-3">
        <h1 className="mr-auto text-xl font-semibold">Publiceren</h1>
        <Select className="w-56" value={companyId} onChange={(e) => changeCompany(e.target.value)} disabled={Boolean(postId)} aria-label="Bedrijf">
          {companies.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
      </div>

      {channels.data?.provider === "mock" && (
        <div className="rounded-md border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
          Testmodus: er wordt niets echt gepost. Zet PUBLISH_PROVIDER=postiz in .env om via Postiz te publiceren.
        </div>
      )}
      {channels.error && <p className="text-sm text-danger">Kanalen ophalen mislukt: {(channels.error as Error).message}</p>}
      {embargo && (
        <div className="flex gap-2 rounded-md border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          Embargo tot {embargo.toLocaleString("nl-NL")}. Direct posten kan niet; plan na die datum in of maak een concept.
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
        <div className="space-y-4">
          <Card className="space-y-3">
            <div className="flex items-center justify-between">
              <Label className="mb-0">1. Beeld of video</Label>
              <input ref={fileInput} type="file" multiple accept="image/*,video/mp4,video/quicktime,.heic" className="hidden" onChange={(e) => { if (e.target.files) void upload(e.target.files); e.target.value = ""; }} />
              <Button size="sm" variant="secondary" onClick={() => fileInput.current?.click()} disabled={!companyId}>
                <Upload size={14} /> Uploaden
              </Button>
            </div>
            {media.length > 0 ? (
              <ul className="flex flex-wrap gap-2">
                {media.map((item) => (
                  <li key={item.id} className="w-28">
                    <button className="relative block w-full" onClick={() => toggleMedia(item)} title="Klik om te verwijderen">
                      {thumb(item, "aspect-square w-full rounded border-2 border-primary")}
                    </button>
                    <div className="mt-1 truncate text-xs text-muted" title={item.label}>{item.formatKey ?? item.label}</div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted">Upload een bestand of kies hieronder uit de bibliotheek. Alleen tekst posten kan ook.</p>
            )}
            {exportJob.data?.result?.files.some((f) => f.severity === "error") && (
              <p className="text-xs text-muted">Exportbestanden met kwaliteitsfouten zijn weggelaten.</p>
            )}
            {(library.data?.length ?? 0) > 0 && (
              <details>
                <summary className="cursor-pointer text-sm text-primary">Uit de bibliotheek kiezen</summary>
                <div className="mt-2 grid grid-cols-4 gap-2 sm:grid-cols-6">
                  {library.data!.map((asset) => {
                    const item = fromAsset(asset);
                    const on = media.some((m) => m.id === item.id);
                    return (
                      <button key={asset.id} className="relative" onClick={() => toggleMedia(item)} aria-pressed={on} title={asset.filename}>
                        {thumb(item, cn("aspect-square w-full rounded border-2", on ? "border-primary" : "border-transparent"))}
                        {on && <Check size={14} className="absolute right-1 top-1 rounded bg-primary text-primary-foreground" />}
                      </button>
                    );
                  })}
                </div>
              </details>
            )}
            {error && <p className="text-sm text-danger">{error}</p>}
          </Card>

          <Card className="space-y-2">
            <Label htmlFor="caption">2. Tekst</Label>
            <Textarea id="caption" rows={6} value={caption} onChange={(e) => setCaption(e.target.value)} placeholder="Tekst bij de post, met hashtags" />
            <p className={cn("text-right text-xs", tooLong ? "text-danger" : "text-muted")}>
              {caption.length}{Number.isFinite(limit) ? ` / ${limit}` : ""} tekens
            </p>
          </Card>
        </div>

        <div className="space-y-4">
          <Card className="space-y-3">
            <Label className="mb-0">3. Kanalen</Label>
            {channels.data && !channels.data.matchedCompany && channels.data.provider === "postiz" && (
              <p className="text-xs text-muted">
                Geen kanalen gevonden voor dit bedrijf. Je ziet alle kanalen. Maak in Postiz een klant met dezelfde naam als het bedrijf om ze te groeperen.
              </p>
            )}
            {channels.data?.channels.length === 0 && <p className="text-sm text-muted">Nog geen kanalen gekoppeld in Postiz.</p>}
            <ul className="space-y-3">
              {channels.data?.channels.map((channel) => {
                const on = channelIds.includes(channel.id);
                return (
                  <li key={channel.id}>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={on}
                        disabled={channel.disabled}
                        onChange={(e) => setChannelIds(e.target.checked ? [...channelIds, channel.id] : channelIds.filter((id) => id !== channel.id))}
                      />
                      {channel.picture && <img src={channel.picture} alt="" className="h-5 w-5 rounded-full" />}
                      {channel.name}
                      <Badge>{channel.platform}</Badge>
                      {channel.disabled && <Badge tone="warning">uit</Badge>}
                    </label>
                    {on && media.length > 1 && (
                      <div className="ml-6 mt-1 flex flex-wrap gap-1" aria-label={`Bestanden voor ${channel.name}`}>
                        {media.map((item) => {
                          const used = mediaFor(channel).includes(item.id);
                          return (
                            <button key={item.id} onClick={() => toggleChannelMedia(channel, item.id)} aria-pressed={used} title={item.formatKey ?? item.label}>
                              {thumb(item, cn("h-10 w-10 rounded border-2", used ? "border-primary" : "border-transparent opacity-40"))}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </Card>

          <Card className="space-y-3">
            <Label className="mb-0">4. Wanneer</Label>
            <div className="flex flex-wrap gap-4 text-sm">
              {(["now", "schedule", "draft"] as const).map((value) => (
                <label key={value} className="flex items-center gap-1.5">
                  <input type="radio" checked={mode === value} onChange={() => setMode(value)} />
                  {{ now: "Nu posten", schedule: "Inplannen", draft: "Concept in Postiz" }[value]}
                </label>
              ))}
            </div>
            {mode === "schedule" && (
              <Input type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} aria-label="Datum en tijd" />
            )}
            <Button className="w-full" onClick={submit} disabled={!canSubmit}>
              <Send size={16} /> {mode === "draft" ? "Concept aanmaken" : mode === "schedule" ? "Inplannen" : "Nu posten"}
            </Button>
            {current && (
              <p className={cn("text-sm", current.status === "failed" ? "text-danger" : "text-muted")}>
                {STATUS[current.status]}{current.error && `: ${current.error}`}
              </p>
            )}
          </Card>
        </div>
      </div>

      <Card>
        <Label>Geschiedenis</Label>
        {history.data?.length ? (
          <ul className="divide-y divide-border text-sm">
            {history.data.map((job) => (
              <li key={job.id} className="flex flex-wrap items-center gap-2 py-2">
                <Badge tone={job.status === "done" ? "success" : job.status === "failed" ? "danger" : "neutral"}>{STATUS[job.status]}</Badge>
                <Badge>{MODE[job.mode]}</Badge>
                {job.provider === "mock" && <Badge tone="warning">test</Badge>}
                <span className="text-muted">{new Date(job.date).toLocaleString("nl-NL")}</span>
                <span>{job.channels.join(", ")}</span>
                <span className="min-w-0 flex-1 truncate text-muted" title={job.caption}>{job.caption || job.files.join(", ")}</span>
                {job.error && <span className="w-full text-xs text-danger">{job.error}</span>}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">Nog niets gepubliceerd voor dit bedrijf.</p>
        )}
      </Card>
    </div>
  );
}
