import type { HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-lg border border-border bg-surface p-4", className)} {...props} />;
}

export function Badge({ className, tone = "neutral", ...props }: HTMLAttributes<HTMLSpanElement> & { tone?: "neutral" | "warning" | "danger" | "success" }) {
  const tones = {
    neutral: "bg-surface-2 text-muted",
    warning: "bg-warning/15 text-warning",
    danger: "bg-danger/15 text-danger",
    success: "bg-success/15 text-success",
  };
  return <span className={cn("inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium", tones[tone], className)} {...props} />;
}
