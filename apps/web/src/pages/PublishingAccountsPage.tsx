import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, PauseCircle, X } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Badge, Card } from "../components/ui/card";
import { Dialog } from "../components/ui/dialog";
import { Input, Label, Select } from "../components/ui/input";
import { api } from "../lib/api";
import type { Company, PublishingSettings, SocialAccount, User } from "../lib/types";
import { toDetail } from "../publishing/ScheduleDialog";
import { WEEKDAYS, fmt } from "../publishing/time";

const MESSAGES: Record<string, { tone: "success" | "warning" | "danger"; text: string }> = {
  geannuleerd: { tone: "warning", text: "Koppelen geannuleerd. Er is niets gewijzigd." },
  verlopen: { tone: "danger", text: "Die koppelpoging is verlopen. Begin opnieuw." },
  mislukt: { tone: "danger", text: "Koppelen is mislukt. Probeer het opnieuw; blijft het misgaan, kijk dan in de API-log." },
};

export function PublishingAccountsPage({ user }: { user: User }) {
  const [params, setParams] = useSearchParams();
  const queryClient = useQueryClient();
  const companies = useQuery({ queryKey: ["companies"], queryFn: () => api.get<Company[]>("/api/companies") });
  const companyId = params.get("bedrijf") ?? companies.data?.[0]?.id ?? "";
  const settings = useQuery({
    queryKey: ["publishing-settings", companyId],
    queryFn: () => api.get<PublishingSettings>(`/api/companies/${companyId}/publishing`),
    enabled: Boolean(companyId),
  });
  const isAdmin = user.role === "admin";
  const message = MESSAGES[params.get("melding") ?? ""];
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["publishing-settings", companyId] });

  return (
    <div className="h-full space-y-6 overflow-y-auto p-6">
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <h1 className="text-xl font-semibold">Accounts en publicatietijden</h1>
          <p className="text-sm text-muted">Per bedrijf: waar naartoe gepubliceerd wordt en op welke vaste tijden.</p>
        </div>
        <div className="ml-auto">
          <Label htmlFor="company">Bedrijf</Label>
          <Select id="company" className="w-56" value={companyId} onChange={(e) => setParams({ bedrijf: e.target.value })}>
            {companies.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
        </div>
      </div>
      {message && (
        <p role="status" className={`rounded-md border p-3 text-sm ${message.tone === "danger" ? "border-danger/40 bg-danger/10 text-danger" : "border-warning/40 bg-warning/10 text-warning"}`}>
          {message.text}
        </p>
      )}
      {params.get("kiezen") && isAdmin && <PendingPicker companyId={companyId} onDone={() => { setParams({ bedrijf: companyId }); void refresh(); }} />}
      {settings.data && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="space-y-4">
            <h2 className="font-semibold">Gekoppelde accounts</h2>
            {settings.data.accounts.length === 0 && <p className="text-sm text-muted">Nog geen accounts gekoppeld.</p>}
            <ul className="divide-y divide-border">
              {settings.data.accounts.map((a) => <AccountRow key={a.id} account={a} isAdmin={isAdmin} onChange={refresh} />)}
            </ul>
            {isAdmin && <ConnectButtons companyId={companyId} settings={settings.data} onChange={refresh} />}
          </Card>
          <Card className="space-y-4">
            <h2 className="font-semibold">Tijdzone en publicatietijden</h2>
            <TimezoneForm companyId={companyId} zone={settings.data.timezone} isAdmin={isAdmin} onChange={refresh} />
            <SlotsEditor companyId={companyId} settings={settings.data} isAdmin={isAdmin} onChange={refresh} />
          </Card>
        </div>
      )}
    </div>
  );
}

function AccountRow({ account, isAdmin, onChange }: { account: SocialAccount; isAdmin: boolean; onChange: () => void }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [understood, setUnderstood] = useState(false);

  const check = async () => {
    setBusy(true);
    try {
      const r = await api.post<{ ok: boolean; message: string }>(`/api/publishing/accounts/${account.id}/check`);
      setResult(r.message);
      onChange();
    } catch (e) {
      setResult(toDetail(e).message);
    } finally {
      setBusy(false);
    }
  };
  const disconnect = async () => {
    setBusy(true);
    try {
      const r = await api.post<{ cancelled: number }>(`/api/publishing/accounts/${account.id}/disconnect`, { confirm: true });
      setResult(`Ontkoppeld; ${r.cancelled} geplande publicatie(s) geannuleerd.`);
      setConfirming(false);
      onChange();
    } catch (e) {
      setResult(toDetail(e).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="space-y-2 py-3">
      <div className="flex items-center gap-2">
        <span className="font-medium">{account.name}</span>
        <Badge>{account.providerLabel}</Badge>
        {account.status === "active" ? (
          <Badge tone="success"><Check size={12} className="mr-1" /> Verbonden</Badge>
        ) : (
          <Badge tone="danger"><PauseCircle size={12} className="mr-1" /> Opnieuw koppelen</Badge>
        )}
      </div>
      {account.status === "reauth_required" && (
        <p className="flex gap-2 text-sm text-warning">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          Publiceren naar dit account staat stil. {account.statusReason ? `Meta meldde: "${account.statusReason}". ` : ""}
          Koppel opnieuw via "Facebook en Instagram koppelen". Te laat geworden publicaties worden niet alsnog verstuurd.
        </p>
      )}
      <p className="text-xs text-muted">Laatst gecontroleerd: {account.lastCheckedAt ? fmt(account.lastCheckedAt, Intl.DateTimeFormat().resolvedOptions().timeZone) : "nooit"}</p>
      <div className="flex gap-2">
        <Button size="sm" variant="secondary" onClick={check} disabled={busy}>Verbinding controleren</Button>
        {isAdmin && <Button size="sm" variant="ghost" className="text-danger" onClick={() => setConfirming(true)}>Ontkoppelen...</Button>}
      </div>
      {result && <p role="status" className="text-xs text-muted">{result}</p>}
      <Dialog open={confirming} onOpenChange={setConfirming} title={`${account.name} ontkoppelen?`}>
        <div className="space-y-3 text-sm">
          <p>De opgeslagen toegang wordt direct verwijderd.</p>
          <p>Alle <strong>geplande</strong> publicaties naar dit account worden geannuleerd. De publicatiegeschiedenis blijft bewaard. Op {account.providerLabel} zelf wordt niets verwijderd.</p>
          <label className="flex items-center gap-2"><input type="checkbox" checked={understood} onChange={(e) => setUnderstood(e.target.checked)} /> Ik begrijp het</label>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setConfirming(false)}>Gekoppeld laten</Button>
            <Button variant="danger" onClick={disconnect} disabled={!understood || busy}>Ontkoppelen</Button>
          </div>
        </div>
      </Dialog>
    </li>
  );
}

function ConnectButtons({ companyId, settings, onChange }: { companyId: string; settings: PublishingSettings; onChange: () => void }) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const connectSandbox = async () => {
    setError(null);
    try {
      await api.post("/api/publishing/connect/sandbox", { companyId, name });
      setName("");
      onChange();
    } catch (e) {
      setError(toDetail(e).message);
    }
  };
  return (
    <div className="space-y-3 border-t border-border pt-4">
      {settings.metaConfigured ? (
        <a href={`/api/publishing/connect/meta/start?company_id=${companyId}`}>
          <Button>Facebook en Instagram koppelen</Button>
        </a>
      ) : (
        <p className="text-sm text-muted">Facebook en Instagram koppelen kan zodra META_APP_ID en META_APP_SECRET zijn ingesteld (zie docs/publiceren.md).</p>
      )}
      <p className="text-xs text-muted">Je logt in bij Facebook en kiest daarna welke pagina's en Instagram-accounts bij dit bedrijf horen. Instagram moet een Business- of Creator-account zijn, gekoppeld aan de Facebook-pagina.</p>
      {settings.sandboxEnabled && (
        <div className="flex items-end gap-2">
          <div>
            <Label htmlFor="sbx-name">Sandbox-account (alleen testen)</Label>
            <Input id="sbx-name" value={name} onChange={(e) => setName(e.target.value.toLowerCase())} placeholder="bijv. klanttest" className="w-48" />
          </div>
          <Button variant="secondary" onClick={connectSandbox} disabled={name.length < 2}>Toevoegen</Button>
        </div>
      )}
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
    </div>
  );
}

function PendingPicker({ companyId, onDone }: { companyId: string; onDone: () => void }) {
  const pending = useQuery({
    queryKey: ["pending-accounts", companyId],
    queryFn: () => api.get<{ provider: string; externalId: string; name: string }[]>(`/api/publishing/connect/pending?company_id=${companyId}`),
  });
  const [chosen, setChosen] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const confirm = async () => {
    try {
      await api.post("/api/publishing/connect/confirm", { companyId, externalIds: chosen });
      onDone();
    } catch (e) {
      setError(toDetail(e).message);
    }
  };
  return (
    <Card className="space-y-3 border-primary/50">
      <h2 className="font-semibold">Welke accounts horen bij dit bedrijf?</h2>
      {pending.data?.length === 0 && <p className="text-sm text-muted">Geen pagina's gevonden waarop je mag publiceren, of de keuze is verlopen. Koppel opnieuw.</p>}
      <ul className="space-y-1">
        {pending.data?.map((a) => (
          <li key={a.externalId}>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={chosen.includes(a.externalId)} onChange={() => setChosen((c) => (c.includes(a.externalId) ? c.filter((x) => x !== a.externalId) : [...c, a.externalId]))} />
              {a.name} <Badge>{a.provider === "instagram" ? "Instagram" : "Facebook-pagina"}</Badge>
            </label>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted">Kies alleen de accounts van dit bedrijf. Deze keuze is 10 minuten geldig.</p>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      <div className="flex gap-2">
        <Button onClick={confirm} disabled={chosen.length === 0}>Koppelen</Button>
        <Button variant="secondary" onClick={onDone}><X size={14} /> Niet nu</Button>
      </div>
    </Card>
  );
}

function TimezoneForm({ companyId, zone, isAdmin, onChange }: { companyId: string; zone: string; isAdmin: boolean; onChange: () => void }) {
  const zones = Intl.supportedValuesOf("timeZone");
  const [value, setValue] = useState(zone);
  const [msg, setMsg] = useState<string | null>(null);
  const save = async () => {
    try {
      await api.put(`/api/companies/${companyId}/timezone`, { timezone: value });
      setMsg("Opgeslagen. Bestaande publicaties houden hun exacte moment.");
      onChange();
    } catch (e) {
      setMsg(toDetail(e).message);
    }
  };
  return (
    <div>
      <Label htmlFor="tz">Tijdzone</Label>
      <div className="flex gap-2">
        <Select id="tz" value={value} onChange={(e) => setValue(e.target.value)} disabled={!isAdmin}>
          {(zones.includes(zone) ? zones : [zone, ...zones]).map((z) => <option key={z} value={z}>{z}</option>)}
        </Select>
        {isAdmin && <Button variant="secondary" onClick={save} disabled={value === zone}>Opslaan</Button>}
      </div>
      {msg && <p role="status" className="mt-1 text-xs text-muted">{msg}</p>}
    </div>
  );
}

function SlotsEditor({ companyId, settings, isAdmin, onChange }: { companyId: string; settings: PublishingSettings; isAdmin: boolean; onChange: () => void }) {
  const [days, setDays] = useState<number[]>([1, 2, 3, 4, 5]);
  const [time, setTime] = useState("09:00");
  const [msg, setMsg] = useState<string | null>(null);
  const add = async () => {
    try {
      const r = await api.post<{ added: number }>(`/api/companies/${companyId}/slots`, { weekdays: days, time });
      setMsg(r.added ? `${r.added} tijd(en) toegevoegd.` : "Die tijden bestonden al.");
      onChange();
    } catch (e) {
      setMsg(toDetail(e).message);
    }
  };
  const remove = async (id: string) => {
    await api.delete(`/api/companies/${companyId}/slots/${id}`);
    onChange();
  };
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted">"Volgende vrije tijd" kiest hieruit. Elk account krijgt één publicatie per tijd. Een tijd verwijderen verplaatst geen geplande publicaties.</p>
      <table className="w-full text-sm">
        <caption className="sr-only">Publicatietijden per weekdag</caption>
        <tbody>
          {WEEKDAYS.map((name, i) => {
            const slots = settings.slots.filter((s) => s.weekday === i + 1);
            return (
              <tr key={name} className="border-t border-border first:border-0">
                <th scope="row" className="w-28 py-1.5 text-left font-medium">{name}</th>
                <td className="py-1.5">
                  {slots.length === 0 ? <span className="text-muted">Geen tijden</span> : (
                    <span className="flex flex-wrap gap-1.5">
                      {slots.map((s) => (
                        <span key={s.id} className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 tabular-nums">
                          {s.time}
                          {isAdmin && <button type="button" aria-label={`${name} ${s.time} verwijderen`} onClick={() => remove(s.id)} className="text-muted hover:text-danger"><X size={12} /></button>}
                        </span>
                      ))}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {isAdmin && (
        <fieldset className="space-y-2">
          <legend className="text-xs font-medium uppercase tracking-wide text-muted">Tijd toevoegen op</legend>
          <div className="flex flex-wrap gap-1.5">
            {WEEKDAYS.map((name, i) => (
              <label key={name} className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-sm">
                <input type="checkbox" checked={days.includes(i + 1)} onChange={() => setDays((d) => (d.includes(i + 1) ? d.filter((x) => x !== i + 1) : [...d, i + 1]))} />
                {name.slice(0, 2)}
              </label>
            ))}
          </div>
          <div className="flex items-end gap-2">
            <div>
              <Label htmlFor="slot-time">Tijd</Label>
              <Input id="slot-time" type="time" value={time} onChange={(e) => setTime(e.target.value)} className="w-32" />
            </div>
            <Button variant="secondary" onClick={add} disabled={days.length === 0}>Toevoegen</Button>
          </div>
          {msg && <p role="status" className="text-xs text-muted">{msg}</p>}
        </fieldset>
      )}
    </div>
  );
}
