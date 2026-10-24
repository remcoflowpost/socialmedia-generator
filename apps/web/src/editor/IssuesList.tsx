import type { QualityIssue } from "@flow/schema";
import { AlertTriangle, CircleX } from "lucide-react";

export function IssuesList({ issues, empty = "Geen meldingen voor dit formaat." }: { issues: QualityIssue[]; empty?: string }) {
  if (issues.length === 0) return <p className="text-sm text-success">{empty}</p>;
  const sorted = [...issues].sort((a, b) => (a.severity === b.severity ? 0 : a.severity === "error" ? -1 : 1));
  return (
    <ul className="space-y-1.5">
      {sorted.map((issue, index) => (
        <li key={index} className="flex gap-2 text-sm">
          {issue.severity === "error" ? (
            <CircleX size={16} className="mt-0.5 shrink-0 text-danger" />
          ) : (
            <AlertTriangle size={16} className="mt-0.5 shrink-0 text-warning" />
          )}
          <span>{issue.message}</span>
        </li>
      ))}
    </ul>
  );
}
