import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Badge, Card } from "../components/ui/card";
import { Label, Select } from "../components/ui/input";
import { api } from "../lib/api";
import type { AttemptRow, Company, Publication } from "../lib/types";
import { RetryButton } from "../publishing/RetryButton";
import { addDays, fmt, localDate } from "../publishing/time";

const OUTCOME: Record<AttemptRow["outcome"], { tone: "success" | "danger" | "warning" | "neutral"; label: string }> = {
  succeeded: { tone: "success", label: "Gelukt" },
  failed: { tone: "danger", label: "Mislukt" },
  uncertain: { tone: "warning", label: "Onbevestigd" },
  in_progress: { tone: "neutral", label: "Bezig" },
};

const TRIGGER: Record<string, string> = {
  schedule: "gepland",
  auto_retry: "automatisch opnieuw",
  manual_retry: "handmatig opnieuw",
};

export function PublicationLogPage() {
  const [params, setParams] = useSearchParams();
  const companies = useQuery({ queryKey: ["companies"], queryFn: () => api.get<Company[]>("/api/companies") });
  const companyId = params.get("bedrijf") ?? companies.data?.[0]?.id ?? "";
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const today = localDate(new Date(), zone);
  const failed = useQuery({
    queryKey: ["publications", companyId, "failed"],
    queryFn: () =>
      api.get<{ failed: Publication[]; timezone: string }>(
        `/api/publications?company_id=${companyId}&start=${addDays(today, -1)}T00:00:00Z&end=${addDays(today, 1)}T00:00:00Z`,
      ),
    enabled: Boolean(companyId),
  });
  const log = useQuery({
    queryKey: ["publication-log", companyId],
    queryFn: () => api.get<AttemptRow[]>(`/api/publications/log?company_id=${companyId}`),
    enabled: Boolean(companyId),
  });
  const tz = failed.data?.timezone ?? zone;

  return (
    <div className="h-full space-y-6 overflow-y-auto p-6">
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <h1 className="text-xl font-semibold">Publicatielog</h1>
          <p className="text-sm text-muted">Elke poging om te publiceren, met wat het netwerk antwoordde. Tijden in {tz}.</p>
        </div>
        <div className="ml-auto">
          <Label htmlFor="company">Bedrijf</Label>
          <Select id="company" className="w-56" value={companyId} onChange={(e) => setParams({ bedrijf: e.target.value })}>
            {companies.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
        </div>
      </div>

      {(failed.data?.failed.length ?? 0) > 0 && (
        <Card className="space-y-3">
          <h2 className="font-semibold">Aandacht nodig ({failed.data!.failed.length})</h2>
          <ul className="divide-y divide-border">
            {failed.data!.failed.map((p) => (
              <li key={p.id} id={`publicatie-${p.id}`} className="flex flex-wrap gap-4 py-3">
                <div className="min-w-64 flex-1 space-y-1 text-sm">
                  <p className="flex items-center gap-2"><Badge tone="danger">Mislukt</Badge> <strong>{p.account.name}</strong> <span className="text-muted">gepland {fmt(p.scheduledAt, tz)}</span></p>
                  <p>{p.postTitle} &middot; {p.formatKey}</p>
                  <p className="text-danger">{p.failureMessage}</p>
                  <p className="text-xs text-muted">{p.attemptCount} poging(en)</p>
                </div>
                <div className="w-64"><RetryButton pub={p} /></div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card className="overflow-x-auto p-0">
        <h2 className="p-4 pb-2 font-semibold">Pogingen</h2>
        {log.data?.length === 0 && <p className="p-4 text-sm text-muted">Nog geen pogingen. Ze verschijnen hier zodra de eerste geplande publicatie aan de beurt is.</p>}
        {(log.data?.length ?? 0) > 0 && (
          <table className="w-full text-sm">
            <caption className="sr-only">Publicatiepogingen, nieuwste eerst</caption>
            <thead className="text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th scope="col" className="px-4 py-2">Moment</th>
                <th scope="col" className="px-4 py-2">Post</th>
                <th scope="col" className="px-4 py-2">Account</th>
                <th scope="col" className="px-4 py-2">Resultaat</th>
                <th scope="col" className="px-4 py-2">Netwerk meldde</th>
                <th scope="col" className="px-4 py-2">Poging</th>
              </tr>
            </thead>
            <tbody>
              {log.data?.map((a) => (
                <tr key={a.id} className="border-t border-border align-top">
                  <td className="whitespace-nowrap px-4 py-2 tabular-nums">{fmt(a.startedAt, tz)}</td>
                  <td className="px-4 py-2">{a.postTitle}<br /><span className="text-xs text-muted">{a.formatKey}</span></td>
                  <td className="px-4 py-2">{a.account.name}</td>
                  <td className="px-4 py-2">
                    <Badge tone={OUTCOME[a.outcome].tone}>{OUTCOME[a.outcome].label}</Badge>
                    {a.errorCode && <p className="mt-1 font-mono text-xs text-muted">{a.errorCode}{a.httpStatus ? ` · HTTP ${a.httpStatus}` : ""}</p>}
                  </td>
                  <td className="max-w-md px-4 py-2 text-muted">
                    {a.providerUrl && <a href={a.providerUrl} target="_blank" rel="noopener noreferrer" className="text-primary underline">Bekijk gepubliceerde post</a>}
                    {a.outcome !== "succeeded" && a.providerMessage}
                    {a.outcome === "succeeded" && a.providerMessage && <p className="text-xs">{a.providerMessage}</p>}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2">#{a.attemptNo} <span className="text-xs text-muted">{TRIGGER[a.trigger] ?? a.trigger}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
