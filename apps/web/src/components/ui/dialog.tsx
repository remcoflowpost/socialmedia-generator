import * as RadixDialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";

export function Dialog({
  open,
  onOpenChange,
  title,
  children,
  wide = false,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-40 bg-black/60" />
        <RadixDialog.Content
          className={`fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[95vw] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-lg border border-border bg-surface p-6 ${wide ? "max-w-5xl" : "max-w-lg"}`}
        >
          <div className="mb-4 flex items-center justify-between">
            <RadixDialog.Title className="text-lg font-semibold">{title}</RadixDialog.Title>
            <RadixDialog.Close className="rounded p-1 text-muted hover:bg-surface-2" aria-label="Sluiten">
              <X size={18} />
            </RadixDialog.Close>
          </div>
          <RadixDialog.Description className="sr-only">{title}</RadixDialog.Description>
          {children}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
