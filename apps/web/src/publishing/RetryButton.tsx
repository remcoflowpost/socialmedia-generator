import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { api } from "../lib/api";
import type { Publication } from "../lib/types";
import { toDetail } from "./ScheduleDialog";

/**
 * Handmatig opnieuw proberen. Bij een onzekere uitkomst moet de gebruiker bevestigen dat
 * de post niet al online staat; de API dwingt dit ook af en controleert zelf nog eens.
 */
export function RetryButton({ pub, compact = false }: { pub: Publication; compact?: boolean }) {
  const queryClient = useQueryClient();
  const [confirmed, setConfirmed] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (pub.account.status !== "active") {
    return (
      <Link to={`/publiceren/accounts?bedrijf=${pub.account.companyId}`} className="text-xs text-primary underline">
        Account opnieuw koppelen
      </Link>
    );
  }
  if (pub.failureCode === "validation" || pub.failureCode === "not_publishable") {
    return (
      <Link to={`/posts/${pub.postId}`} className="text-xs text-primary underline">
        Post aanpassen
      </Link>
    );
  }

  const retry = async () => {
    setBusy(true);
    setMessage(null);
    try {
      await api.post(`/api/publications/${pub.id}/retry`, { version: pub.version, confirmed });
      setMessage("Opnieuw ingepland; binnen een minuut verstuurd.");
      await queryClient.invalidateQueries({ queryKey: ["publications"] });
      await queryClient.invalidateQueries({ queryKey: ["publication-log"] });
    } catch (e) {
      setMessage(toDetail(e).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-1">
      {pub.needsConfirm && (
        <label className="flex items-start gap-1.5 text-xs">
          <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} className="mt-0.5" />
          <span>Ik heb {pub.account.name} gecontroleerd: de post staat er niet.</span>
        </label>
      )}
      <Button size="sm" variant={compact ? "secondary" : "default"} onClick={retry} disabled={busy || (pub.needsConfirm && !confirmed)}>
        {busy ? "Bezig..." : "Opnieuw proberen"}
      </Button>
      {message && <p role="status" className="text-xs text-muted">{message}</p>}
    </div>
  );
}
