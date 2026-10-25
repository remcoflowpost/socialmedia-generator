import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ChevronLeft, ChevronRight, ExternalLink, GripVertical } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/card";
import { Dialog } from "../components/ui/dialog";
import { Input, Label, Select, Textarea } from "../components/ui/input";
import { api } from "../lib/api";
import { cn } from "../lib/cn";
import type { Company, Publication, PublishErrorDetail } from "../lib/types";
import { RetryButton } from "../publishing/RetryButton";
import { toDetail } from "../publishing/ScheduleDialog";
import { STATUS_LABEL, addDays, fmt, localDate, localTime, mondayOf } from "../publishing/time";

interface WeekData {
  timezone: string;
  publications: Publication[];
  failed: Publication[];
  slots: string[];
}

type Target = { iso: string } | { date: string };

export function PlanningPage() {
  const [params, setParams] = useSearchParams();
  const companies = useQuery({ queryKey: ["companies"], queryFn: () => api.get<Company[]>("/api/companies") });
  const companyId = params.get("bedrijf") ?? companies.data?.[0]?.id ?? "";
  // Standaardweek op basis van de browser; "vandaag" hieronder in de zone van het bedrijf.
  const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const week = mondayOf(params.get("week") ?? localDate(new Date(), browserZone));
  const days = Array.from({ length: 7 }, (_, i) => addDays(week, i));

  // Ruim opvragen (een dag extra aan beide kanten) en daarna filteren op de lokale datum
  // in de zone van het bedrijf: zo hoeft de browser geen tijdzone-rekenwerk te doen.
  const data = useQuery({
    queryKey: ["publications", companyId, week],
    queryFn: () =>
      api.get<WeekData>(
        `/api/publications?company_id=${companyId}&start=${addDays(week, -1)}T00:00:00Z&end=${addDays(week, 8)}T00:00:00Z`,
      ),
    enabled: Boolean(companyId),
  });
  const zone = data.data?.timezone ?? browserZone;
  const today = localDate(new Date(), zone);
  const [move, setMove] = useState<{ pub: Publication; target: Target } | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);
  const [announce, setAnnounce] = useState("");

  const byDay = useMemo(() => {
    const out: Record<string, { pubs: Publication[]; slots: string[] }> = Object.fromEntries(days.map((d) => [d, { pubs: [], slots: [] }]));
    for (const p of data.data?.publications ?? []) {
      const d = p.scheduledAt ? localDate(p.scheduledAt, zone) : null;
      if (d && out[d]) out[d].pubs.push(p);
    }
    const taken = new Set((data.data?.publications ?? []).filter((p) => p.status === "scheduled").map((p) => p.scheduledAt));
    for (const s of data.data?.slots ?? []) {
      const d = localDate(s, zone);
      if (out[d] && new Date(s) > new Date() && !taken.has(s)) out[d].slots.push(s);
    }
    return out;
  }, [data.data, days, zone]);

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    next.set(key, value);
    setParams(next);
  };
  const pubById = (id: string) => data.data?.publications.find((p) => p.id === id) ?? data.data?.failed.find((p) => p.id === id);
  const drop = (target: Target) => (e: React.DragEvent) => {
    e.preventDefault();
    const pub = pubById(e.dataTransfer.getData("text/publication"));
    setDragging(null);
    if (pub) setMove({ pub, target });
  };
  const allowDrop = (e: React.DragEvent) => {
    if (e.dataTransfer.types.includes("text/publication")) e.preventDefault();
  };

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-6">
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <h1 className="text-xl font-semibold">Planning</h1>
          <p className="text-sm text-muted">Tijden in {zone}. Sleep een publicatie naar een andere tijd of dag, of gebruik "Verplaatsen".</p>
        </div>
        <div className="ml-auto flex items-end gap-2">
          <div>
            <Label htmlFor="company">Bedrijf</Label>
            <Select id="company" value={companyId} onChange={(e) => set("bedrijf", e.target.value)} className="w-56">
              {companies.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          </div>
          <nav className="flex items-center gap-1" aria-label="Week">
            <Button variant="secondary" size="sm" aria-label="Vorige week" onClick={() => set("week", addDays(week, -7))}><ChevronLeft size={16} /></Button>
            <span className="min-w-40 text-center text-sm font-medium" aria-live="polite">
              {fmt(`${week}T12:00:00Z`, "UTC", "day")} – {fmt(`${addDays(week, 6)}T12:00:00Z`, "UTC", "day")}
            </span>
            <Button variant="secondary" size="sm" aria-label="Volgende week" onClick={() => set("week", addDays(week, 7))}><ChevronRight size={16} /></Button>
          </nav>
        </div>
      </div>

      {(data.data?.failed.length ?? 0) > 0 && (
        <div className="flex items-center gap-2 rounded-md border border-danger/40 bg-danger/10 p-3 text-sm text-danger" role="status">
          <AlertTriangle size={16} />
          {data.data!.failed.length} publicatie(s) mislukt. <Link to={`/publiceren/log?bedrijf=${companyId}`} className="underline">Bekijk en probeer opnieuw</Link>.
        </div>
      )}
      {data.isLoading && <p className="text-sm text-muted">Laden...</p>}
      {data.error && <p className="text-sm text-danger">{(data.error as Error).message}</p>}

      <div className="grid gap-2 lg:grid-cols-7">
        {days.map((d) => {
          const past = d < today;
          const day = byDay[d] ?? { pubs: [], slots: [] };
          const entries = [
            ...day.slots.map((s) => ({ kind: "slot" as const, at: s })),
            ...day.pubs.map((p) => ({ kind: "pub" as const, at: p.scheduledAt!, p })),
          ].sort((a, b) => a.at.localeCompare(b.at));
          return (
            <section
              key={d}
              aria-label={fmt(`${d}T12:00:00Z`, "UTC", "day")}
              onDragOver={past ? undefined : allowDrop}
              onDrop={past ? undefined : drop({ date: d })}
              className={cn("flex min-h-64 flex-col rounded-lg border border-border bg-surface", past && "opacity-60", d === today && "ring-1 ring-primary/50")}
            >
              <h2 className="flex justify-between border-b border-border px-3 py-2 text-sm">
                <span className="font-medium capitalize">{fmt(`${d}T12:00:00Z`, "UTC", "day")}</span>
                {d === today && <span className="text-xs text-primary">Vandaag</span>}
              </h2>
              <ul className="flex flex-1 flex-col gap-1.5 p-2">
                {entries.length === 0 && <li className="text-xs text-muted">{past ? "Niets gepland." : "Geen vrije publicatietijden."}</li>}
                {entries.map((e) =>
                  e.kind === "slot" ? (
                    <li
                      key={`s${e.at}`}
                      onDragOver={allowDrop}
                      onDrop={(ev) => { ev.stopPropagation(); drop({ iso: e.at })(ev); }}
                      className={cn("rounded border border-dashed border-border px-2 py-1 text-xs text-muted", dragging && "border-primary text-primary")}
                    >
                      {localTime(e.at, zone)} &middot; vrij
                    </li>
                  ) : (
                    <li
                      key={e.p.id}
                      onDragOver={e.p.status === "scheduled" ? allowDrop : undefined}
                      onDrop={e.p.status === "scheduled" ? (ev) => { ev.stopPropagation(); drop({ iso: e.p.scheduledAt! })(ev); } : undefined}
                    >
                      <PubCard pub={e.p} zone={zone} onMove={() => setMove({ pub: e.p, target: { date: d } })} onDragStart={setDragging} />
                    </li>
                  ),
                )}
              </ul>
            </section>
          );
        })}
      </div>

      {move && (
        <MoveDialog
          key={`${move.pub.id}:${JSON.stringify(move.target)}`}
          pub={move.pub}
          target={move.target}
          zone={zone}
          onClose={(message) => { setMove(null); if (message) setAnnounce(message); }}
        />
      )}
      <p className="sr-only" role="status" aria-live="polite">{announce}</p>
    </div>
  );
}

function PubCard({ pub, zone, onMove, onDragStart }: { pub: Publication; zone: string; onMove: () => void; onDragStart: (id: string | null) => void }) {
  const movable = pub.status === "scheduled" || pub.status === "failed";
  const tone = pub.status === "published" ? "success" : pub.status === "failed" ? "danger" : pub.failureCode ? "warning" : "neutral";
  return (
    <article
      draggable={movable}
      onDragStart={(e) => { e.dataTransfer.setData("text/publication", pub.id); e.dataTransfer.effectAllowed = "move"; onDragStart(pub.id); }}
      onDragEnd={() => onDragStart(null)}
      aria-label={`${localTime(pub.scheduledAt!, zone)} ${pub.account.name}: ${pub.postTitle}`}
      className={cn(
        "rounded-md border border-border bg-surface-2 p-2 text-xs",
        movable && "cursor-grab",
        pub.status === "failed" && "border-danger/50",
        pub.status === "published" && "border-success/40",
      )}
    >
      <div className="flex items-center justify-between gap-1">
        <span className="font-semibold tabular-nums">{localTime(pub.scheduledAt!, zone)}</span>
        <Badge tone={tone}>{pub.status === "scheduled" && pub.failureCode ? "Opnieuw proberen" : STATUS_LABEL[pub.status]}</Badge>
      </div>
      <p className="mt-1 truncate text-muted">{pub.account.name} &middot; {pub.account.providerLabel}</p>
      <p className="mt-0.5 line-clamp-2">{pub.postTitle}</p>
      {pub.account.status !== "active" && pub.status === "scheduled" && <p className="mt-1 text-warning">Account gepauzeerd</p>}
      {pub.status === "failed" && pub.failureMessage && <p className="mt-1 line-clamp-3 text-danger">{pub.failureMessage}</p>}
      <div className="mt-1.5 flex flex-wrap items-center gap-2">
        {movable && <GripVertical size={12} className="text-muted" aria-hidden />}
        {movable && <button type="button" className="text-primary underline" onClick={onMove}>Verplaatsen</button>}
        {pub.providerUrl && <a href={pub.providerUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 text-primary underline">Bekijk <ExternalLink size={10} /></a>}
        {pub.status === "failed" && <RetryButton pub={pub} compact />}
      </div>
    </article>
  );
}

type Phase =
  | { k: "checking" }
  | { k: "confirm" }
  | { k: "conflict"; caption: string; otherVersion: number }
  | { k: "fix"; issues: string[] }
  | { k: "error"; message: string };

function MoveDialog({ pub, target, zone, onClose }: { pub: Publication; target: Target; zone: string; onClose: (message?: string) => void }) {
  const queryClient = useQueryClient();
  const [phase, setPhase] = useState<Phase>({ k: "checking" });
  const [date, setDate] = useState("date" in target ? target.date : localDate(target.iso, zone));
  const [time, setTime] = useState("iso" in target ? localTime(target.iso, zone) : pub.scheduledAt ? localTime(pub.scheduledAt, zone) : "09:00");
  const [useSlot, setUseSlot] = useState("iso" in target);
  const [caption, setCaption] = useState(pub.caption);
  const [busy, setBusy] = useState(false);

  const when = () => (useSlot && "iso" in target ? { kind: "instant", instant: target.iso } : { kind: "local", date, time });
  const call = (extra: Record<string, unknown>) =>
    api.post<{ publication: Publication; swappedWith: string | null }>(`/api/publications/${pub.id}/move`, {
      version: pub.version,
      when: when(),
      caption: caption !== pub.caption ? caption : undefined,
      ...extra,
    });

  const handle = (e: unknown) => {
    const detail: PublishErrorDetail = toDetail(e);
    if (detail.conflict) return setPhase({ k: "conflict", caption: detail.conflict.otherCaption, otherVersion: detail.conflict.otherVersion });
    if (detail.issues?.length) return setPhase({ k: "fix", issues: detail.issues });
    setPhase({ k: "error", message: detail.message });
  };

  const check = async () => {
    setBusy(true);
    try {
      await call({ dryRun: true });
      setPhase({ k: "confirm" });
    } catch (e) {
      handle(e);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    void check();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const confirm = async (swap?: number) => {
    setBusy(true);
    try {
      const result = await call(swap ? { onConflict: "swap", otherVersion: swap } : {});
      await queryClient.invalidateQueries({ queryKey: ["publications"] });
      onClose(`${result.swappedWith ? "Omgewisseld" : "Verplaatst"} naar ${fmt(result.publication.scheduledAt, zone)}.`);
    } catch (e) {
      handle(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose("Niets gewijzigd.")} title="Publicatie verplaatsen">
      <div className="space-y-4 text-sm">
        <p className="text-muted">{pub.postTitle} &middot; {pub.account.name}</p>
        {!useSlot && (
          <div className="flex gap-2">
            <div>
              <Label htmlFor="mv-date">Datum</Label>
              <Input id="mv-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-40" />
            </div>
            <div>
              <Label htmlFor="mv-time">Tijd ({zone})</Label>
              <Input id="mv-time" type="time" value={time} onChange={(e) => setTime(e.target.value)} className="w-32" />
            </div>
            <Button variant="secondary" size="sm" className="self-end" onClick={check} disabled={busy}>Controleren</Button>
          </div>
        )}
        <div aria-live="polite">
          {phase.k === "checking" && <p className="text-muted">Tijdstip controleren...</p>}
          {phase.k === "confirm" && (
            <p>
              Nieuw moment: <strong>{useSlot && "iso" in target ? fmt(target.iso, zone) : `${date} ${time}`}</strong> ({zone})
            </p>
          )}
          {phase.k === "conflict" && (
            <div role="alert" className="space-y-2 rounded-md border border-warning/40 bg-warning/10 p-3 text-warning">
              <p className="font-medium">Dat moment is bezet</p>
              <p>Op dit account staat dan al: &ldquo;{phase.caption || "publicatie zonder bijschrift"}&rdquo;. Er is niets gewijzigd. Wissel ze om, of kies een andere tijd.</p>
              {useSlot && <button type="button" className="underline" onClick={() => setUseSlot(false)}>Andere tijd kiezen</button>}
            </div>
          )}
          {phase.k === "fix" && (
            <div role="alert" className="space-y-2 rounded-md border border-danger/40 bg-danger/10 p-3 text-danger">
              {phase.issues.map((m) => <p key={m}>{m}</p>)}
              {phase.issues.some((m) => m.includes("tekens") || m.includes("hashtags")) && (
                <>
                  <Label htmlFor="mv-caption">Bijschrift aanpassen</Label>
                  <Textarea id="mv-caption" value={caption} onChange={(e) => setCaption(e.target.value)} />
                  <Button size="sm" variant="secondary" onClick={check} disabled={busy}>Opnieuw controleren</Button>
                </>
              )}
            </div>
          )}
          {phase.k === "error" && <p role="alert" className="text-danger">{phase.message}</p>}
        </div>
        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button variant="secondary" onClick={() => onClose("Niets gewijzigd.")}>Annuleren</Button>
          {phase.k === "conflict" && <Button onClick={() => confirm(phase.otherVersion)} disabled={busy}>Omwisselen</Button>}
          {phase.k === "confirm" && <Button onClick={() => confirm()} disabled={busy} autoFocus>Verplaatsen</Button>}
        </div>
      </div>
    </Dialog>
  );
}
