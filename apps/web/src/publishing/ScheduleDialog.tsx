import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CalendarClock, Check } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/card";
import { Dialog } from "../components/ui/dialog";
import { Input, Label, Select, Textarea } from "../components/ui/input";
import { api, ApiError } from "../lib/api";
import type { Publication, PublishErrorDetail, PublishOptions } from "../lib/types";
import { fmt, localDate } from "./time";

const FORMAT_LABEL: Record<string, string> = {
  "instagram/feed-square": "Instagram vierkant (1:1)",
  "instagram/feed-portrait": "Instagram portret (4:5)",
  "instagram/story": "Instagram story",
  "facebook/feed-landscape": "Facebook liggend",
  "facebook/feed-square": "Facebook vierkant",
};

/**
 * Inplannen van de laatst opgeslagen versie. De API controleert alle regels opnieuw;
 * deze dialoog laat ze alleen vooraf zien zodat je niet tegen een muur loopt.
 */
export function ScheduleDialog({ open, onOpenChange, postId }: { open: boolean; onOpenChange: (open: boolean) => void; postId: string }) {
  const queryClient = useQueryClient();
  const options = useQuery({
    queryKey: ["publish-options", postId],
    queryFn: () => api.get<PublishOptions>(`/api/posts/${postId}/publish-options`),
    enabled: open,
  });
  const data = options.data;
  const [accountIds, setAccountIds] = useState<string[]>([]);
  const [formats, setFormats] = useState<Record<string, string>>({});
  const [caption, setCaption] = useState("");
  const [whenKind, setWhenKind] = useState<"next_slot" | "local">("next_slot");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("09:00");
  const [approver, setApprover] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<PublishErrorDetail | null>(null);
  const [done, setDone] = useState<Publication[] | null>(null);

  useEffect(() => {
    if (!open) {
      setError(null);
      setDone(null);
    }
  }, [open]);

  const chosen = useMemo(() => data?.accounts.filter((a) => accountIds.includes(a.id)) ?? [], [data, accountIds]);
  const approvedForThis = Boolean(data?.version && data.approval.approved && data.approval.version === data.version.number);
  const storyOnly = chosen.length > 0 && chosen.every((a) => formats[a.provider] === "instagram/story");

  const toggle = (id: string, provider: string, available: string[]) => {
    setAccountIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));
    const first = available[0];
    if (!formats[provider] && first) setFormats((f) => ({ ...f, [provider]: first }));
  };

  const recordApproval = async () => {
    if (!data?.version) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/posts/${postId}/approval`, { approvedBy: approver, version: data.version.number });
      await options.refetch();
    } catch (e) {
      setError(toDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    if (!data?.version) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.post<Publication[]>("/api/publications", {
        postId,
        versionId: data.version.id,
        accountIds,
        formats,
        caption,
        when: whenKind === "next_slot" ? { kind: "next_slot" } : { kind: "local", date, time },
      });
      setDone(created);
      void queryClient.invalidateQueries({ queryKey: ["publications"] });
    } catch (e) {
      setError(toDetail(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Inplannen" wide>
      {options.isLoading && <p className="text-sm text-muted">Laden...</p>}
      {options.error && <p className="text-sm text-danger">{(options.error as Error).message}</p>}
      {data && done && (
        <div className="space-y-3" role="status">
          <p className="flex items-center gap-2 text-success"><Check size={18} /> Ingepland.</p>
          <ul className="space-y-1 text-sm">
            {done.map((p) => (
              <li key={p.id}>{p.account.name}: {fmt(p.scheduledAt, data.timezone)} ({data.timezone})</li>
            ))}
          </ul>
          <div className="flex gap-2">
            <Link
              to={`/publiceren/planning?bedrijf=${done[0]?.account.companyId ?? ""}${done[0]?.scheduledAt ? `&week=${localDate(done[0].scheduledAt, data.timezone)}` : ""}`}
            >
              <Button size="sm">Naar de planning</Button>
            </Link>
            <Button size="sm" variant="secondary" onClick={() => onOpenChange(false)}>Sluiten</Button>
          </div>
        </div>
      )}
      {data && !done && (
        <div className="grid gap-6 md:grid-cols-2">
          <div className="space-y-5">
            <section aria-labelledby="sched-version">
              <h3 id="sched-version" className="mb-2 text-sm font-semibold">Versie</h3>
              {!data.version ? (
                <Notice>Sla eerst een versie op en exporteer die; alleen bevroren versies worden gepubliceerd.</Notice>
              ) : (
                <p className="text-sm">Versie {data.version.number}, geexporteerd in {Object.keys(data.exportedFormats).length} formaten.</p>
              )}
              {data.embargoUntil && new Date(data.embargoUntil) > new Date() && (
                <p className="mt-2 text-sm text-warning">Embargo tot {fmt(data.embargoUntil, data.timezone)}. Eerder inplannen kan niet.</p>
              )}
            </section>

            <section aria-labelledby="sched-approval">
              <h3 id="sched-approval" className="mb-2 text-sm font-semibold">Klantakkoord</h3>
              {approvedForThis ? (
                <p className="flex items-center gap-2 text-sm text-success">
                  <Check size={16} /> Akkoord van {data.approval.by} voor versie {data.approval.version}
                </p>
              ) : (
                <div className="space-y-2">
                  <Notice>
                    {data.approval.approved
                      ? `Er is akkoord voor versie ${data.approval.version}, niet voor versie ${data.version?.number}.`
                      : "Er is nog geen akkoord van de klant."}{" "}
                    Publiceren op klantpagina's kan pas na akkoord op precies deze versie.
                  </Notice>
                  <Label htmlFor="approver">Akkoord gegeven door</Label>
                  <div className="flex gap-2">
                    <Input id="approver" value={approver} onChange={(e) => setApprover(e.target.value)} placeholder="Naam van de contactpersoon" />
                    <Button variant="secondary" onClick={recordApproval} disabled={busy || !approver.trim() || !data.version}>
                      Vastleggen
                    </Button>
                  </div>
                </div>
              )}
            </section>

            <section aria-labelledby="sched-when">
              <h3 id="sched-when" className="mb-2 text-sm font-semibold">Wanneer</h3>
              <div className="space-y-2 text-sm">
                <label className="flex items-center gap-2">
                  <input type="radio" name="when" checked={whenKind === "next_slot"} onChange={() => setWhenKind("next_slot")} />
                  Volgende vrije publicatietijd per account
                </label>
                <label className="flex items-center gap-2">
                  <input type="radio" name="when" checked={whenKind === "local"} onChange={() => setWhenKind("local")} />
                  Specifiek moment
                </label>
                {whenKind === "local" && (
                  <div className="flex gap-2 pl-6">
                    <div>
                      <Label htmlFor="sched-date">Datum</Label>
                      <Input id="sched-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-40" />
                    </div>
                    <div>
                      <Label htmlFor="sched-time">Tijd ({data.timezone})</Label>
                      <Input id="sched-time" type="time" value={time} onChange={(e) => setTime(e.target.value)} className="w-32" />
                    </div>
                  </div>
                )}
              </div>
            </section>
          </div>

          <div className="space-y-5">
            <section aria-labelledby="sched-accounts">
              <h3 id="sched-accounts" className="mb-2 text-sm font-semibold">Accounts</h3>
              {data.accounts.length === 0 && (
                <Notice>
                  Dit bedrijf heeft nog geen gekoppelde accounts. <Link className="underline" to="/publiceren/accounts">Koppel er een</Link>.
                </Notice>
              )}
              <ul className="space-y-2">
                {data.accounts.map((a) => {
                  const disabled = a.status !== "active" || a.formats.length === 0;
                  return (
                    <li key={a.id} className="rounded-md border border-border p-3">
                      <label className="flex items-center gap-2 text-sm">
                        <input type="checkbox" checked={accountIds.includes(a.id)} disabled={disabled} onChange={() => toggle(a.id, a.provider, a.formats)} />
                        <span className="font-medium">{a.name}</span>
                        <Badge>{a.providerLabel}</Badge>
                        {a.status !== "active" && <Badge tone="danger">Opnieuw koppelen</Badge>}
                      </label>
                      {a.formats.length === 0 && a.status === "active" && (
                        <p className="mt-1 pl-6 text-xs text-muted">Geen geexporteerd formaat dat {a.providerLabel} accepteert.</p>
                      )}
                      {a.unsupportedFormats.includes("instagram/feed-3x4") && a.provider === "instagram" && (
                        <p className="mt-1 pl-6 text-xs text-muted">3:4 kan niet via de API naar Instagram; kies 1:1 of 4:5.</p>
                      )}
                      {accountIds.includes(a.id) && (
                        <div className="mt-2 pl-6">
                          <Label htmlFor={`fmt-${a.id}`}>Formaat</Label>
                          <Select id={`fmt-${a.id}`} value={formats[a.provider] ?? ""} onChange={(e) => setFormats((f) => ({ ...f, [a.provider]: e.target.value }))}>
                            {a.formats.map((f) => (
                              <option key={f} value={f}>{FORMAT_LABEL[f] ?? f}</option>
                            ))}
                          </Select>
                          {whenKind === "next_slot" && (
                            <p className="mt-1 text-xs text-muted">
                              {a.nextSlot ? `Volgende vrije tijd: ${fmt(a.nextSlot, data.timezone)}` : "Geen vrije publicatietijd; stel ze in bij Accounts."}
                            </p>
                          )}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>

            <section aria-labelledby="sched-caption">
              <h3 id="sched-caption" className="mb-2 text-sm font-semibold">Bijschrift</h3>
              <Textarea id="caption" aria-labelledby="sched-caption" value={caption} onChange={(e) => setCaption(e.target.value)} disabled={storyOnly} rows={5} />
              {storyOnly && <p className="mt-1 text-xs text-muted">Stories hebben geen bijschrift.</p>}
              <ul className="mt-1 space-y-0.5 text-xs" aria-live="polite">
                {chosen.filter((a) => a.captionLimit && formats[a.provider] !== "instagram/story").map((a) => {
                  const over = [...caption].length - (a.captionLimit ?? 0);
                  return (
                    <li key={a.id} className={over > 0 ? "text-danger" : "text-muted"}>
                      {a.name}: {[...caption].length} / {a.captionLimit} {over > 0 ? `(${over} te veel)` : ""}
                    </li>
                  );
                })}
              </ul>
            </section>

            {error && (
              <div role="alert" className="space-y-1 rounded-md border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
                <p className="flex items-center gap-2 font-medium"><AlertTriangle size={16} /> Niet ingepland</p>
                {(error.issues?.length ? error.issues : [error.message]).map((m) => <p key={m}>{m}</p>)}
              </div>
            )}

            <Button onClick={submit} disabled={busy || !approvedForThis || accountIds.length === 0 || (whenKind === "local" && !date)}>
              <CalendarClock size={16} /> {busy ? "Bezig..." : "Inplannen"}
            </Button>
            {!approvedForThis && <p className="text-xs text-muted">Inplannen kan na klantakkoord op deze versie.</p>}
          </div>
        </div>
      )}
    </Dialog>
  );
}

function Notice({ children }: { children: React.ReactNode }) {
  return <p className="rounded-md border border-warning/40 bg-warning/10 p-3 text-sm text-warning">{children}</p>;
}

export function toDetail(e: unknown): PublishErrorDetail {
  if (e instanceof ApiError && e.detail && typeof e.detail === "object") return e.detail as PublishErrorDetail;
  return { message: (e as Error).message };
}
