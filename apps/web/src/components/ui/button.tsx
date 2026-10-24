import type { ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

type Variant = "default" | "secondary" | "ghost" | "danger";

const variants: Record<Variant, string> = {
  default: "bg-primary text-primary-foreground hover:brightness-110",
  secondary: "bg-surface-2 text-foreground border border-border hover:bg-border",
  ghost: "text-foreground hover:bg-surface-2",
  danger: "bg-danger text-white hover:brightness-110",
};

export function Button({
  className,
  variant = "default",
  size = "md",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md" }) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md font-medium transition disabled:opacity-50 disabled:pointer-events-none",
        size === "sm" ? "h-8 px-3 text-sm" : "h-10 px-4 text-sm",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
