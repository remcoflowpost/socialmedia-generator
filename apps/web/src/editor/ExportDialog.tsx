import type { Format, LayoutReport } from "@flow/schema";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Download } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/card";
import { Dialog } from "../components/ui/dialog";
import { Label } from "../components/ui/input";
import { api } from "../lib/api";
import { formatKey, type Job } from "../lib/types";
import { IssuesList } from "./IssuesList";

export function ExportDialog({
  open,
  onOpenChange,
  postId,
  formats,
  liveReports,
  embargoActive,
  beforeExport,
  onExported,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  postId: string;
  formats: Format[];
  liveReports: Record<string, LayoutReport>;
  embargoActive: boolean;
  beforeExport: () => Promise<boolean>;
  onExported: (version: number) => void;
}) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string[]>(() => formats.map(formatKey));
  const [type, setType] = useState<"jpeg" | "png">("jpeg");
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.get<Job>(`/api/jobs/${jobId}`),
    enabled: Boolean(jobId),
    refetchInterval: (query) => (["done", "failed"].includes(query.state.data?.status ?? "") ? false : 1000),
  });

  const start = async () => {
    setError(null);
    // Eerst de werkkopie opslaan, anders bevriest de export een verouderde stand.
    if (!(await beforeExport())) {
      setError("Opslaan mislukt, export niet gestart.");
      return;
    }
    try {
      const created = await api.post<Job>(`/api/posts/${postId}/export`, { format_keys: selected, type });
      setJobId(created.id);

    } catch (e) {
      setError((e as Error).message);
    }
  };

  // Na een geslaagde export staan de contrastmetingen in de database.
  useEffect(() => {
    if (job.data?.status !== "done" || !job.data.result) return;
    onExported(job.data.result.version);
    void queryClient.invalidateQueries({ queryKey: ["quality", postId] });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job.data?.status, postId, queryClient]);

  const live = selected.flatMap((key) => liveReports[key]?.issues ?? []);
  const errors = live.filter((i) => i.severity === "error").length;
  const done = job.data?.status === "done";

  return (
    <Dialog open={open} onOpenChange={(value) => { onOpenChange(value); if (!value) setJobId(null); }} title="Exporteren" wide>
      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-4">
          {embargoActive && (
            <div className="flex gap-2 rounded-md border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
              <AlertTriangle size={16} className="mt-0.5 shrink-0" />
              Deze post heeft een embargo. Bestandsnamen krijgen EMBARGO_ ervoor. Niet publiceren voor de embargodatum.
            </div>
          )}
          <div>
            <Label>Formaten</Label>
            <div className="mb-2 flex gap-2 text-xs">
              <button className="text-primary" onClick={() => setSelected(formats.map(formatKey))}>Alles</button>
              <button className="text-primary" onClick={() => setSelected([])}>Niets</button>
            </div>
            <div className="grid grid-cols-1 gap-1.5">
              {formats.map((format) => {
                const key = formatKey(format);
                const issues = liveReports[key]?.issues ?? [];
                const hasError = issues.some((i) => i.severity === "error");
                return (
                  <label key={key} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={selected.includes(key)}
                      onChange={(e) => setSelected(e.target.checked ? [...selected, key] : selected.filter((k) => k !== key))}
                    />
                    {format.label}
                    <span className="text-xs text-muted">{format.width}x{format.height}</span>
                    {hasError && <Badge tone="danger">fout</Badge>}
                    {!hasError && issues.length > 0 && <Badge tone="warning">waarschuwing</Badge>}
                  </label>
                );
              })}
            </div>
          </div>
          <div>
            <Label>Bestandstype</Label>
            <div className="flex gap-4 text-sm">
              <label className="flex items-center gap-1.5"><input type="radio" checked={type === "jpeg"} onChange={() => setType("jpeg")} /> JPEG (sRGB, kwaliteit 90)</label>
              <label className="flex items-center gap-1.5"><input type="radio" checked={type === "png"} onChange={() => setType("png")} /> PNG</label>
            </div>
          </div>
          {error && <p className="text-sm text-danger">{error}</p>}
          <Button className="w-full" onClick={start} disabled={selected.length === 0 || (jobId !== null && !done && job.data?.status !== "failed")}>
            {selected.length} formaat/formaten exporteren
          </Button>
          {errors > 0 && (
            <p className="text-xs text-muted">
              Er zijn {errors} kwaliteitsfouten. Downloaden kan, maar de post kan zo niet op "klaar voor publicatie".
            </p>
          )}
        </div>

        <div className="space-y-4">
          {jobId && job.data && (
            <div className="space-y-2">
              <Label>Voortgang</Label>
              <div className="h-2 overflow-hidden rounded bg-surface-2">
                <div className="h-full bg-primary transition-all" style={{ width: `${Math.round(job.data.progress * 100)}%` }} />
              </div>
              <p className="text-sm text-muted">
                {{ queued: "In de wachtrij", running: "Bezig met renderen", done: "Klaar", failed: "Mislukt" }[job.data.status]}
                {job.data.error && `: ${job.data.error}`}
              </p>
              {done && job.data.result && (
                <div className="space-y-2">
                  <a href={`/api/jobs/${jobId}/download`} className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
                    <Download size={16} /> {job.data.result.zipName}
                  </a>
                  <ul className="space-y-1 text-xs">
                    {job.data.result.files.map((file) => (
                      <li key={file.name} className="flex items-center gap-2">
                        <a className="truncate text-primary hover:underline" href={`/api/jobs/${jobId}/download?file=${encodeURIComponent(file.name)}`}>{file.name}</a>
                        {file.severity === "error" && <Badge tone="danger">fout</Badge>}
                        {file.severity === "warning" && <Badge tone="warning">waarschuwing</Badge>}
                      </li>
                    ))}
                  </ul>
                  <p className="text-xs text-muted">Contrastmetingen op de echte pixels staan nu onder "Kwaliteit" in de editor.</p>
                </div>
              )}
            </div>
          )}
          <div>
            <Label>Meldingen (live, geselecteerde formaten)</Label>
            <IssuesList issues={live} empty="Geen meldingen." />
          </div>
        </div>
      </div>
    </Dialog>
  );
}
