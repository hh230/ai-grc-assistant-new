import { cn } from "@/lib/utils";
import type { DocumentStatus } from "@/lib/documents/types";

const STATUS_META: Record<
  DocumentStatus,
  { label: string; dot: string; text: string; pulse?: boolean }
> = {
  uploaded: {
    label: "Ready for analysis",
    dot: "bg-accent-foreground",
    text: "text-foreground-secondary",
  },
  queued: { label: "Queued", dot: "bg-warning", text: "text-foreground-secondary" },
  processing: {
    label: "Processing",
    dot: "bg-accent-foreground",
    text: "text-foreground-secondary",
    pulse: true,
  },
  processed: { label: "Processed", dot: "bg-success", text: "text-foreground-secondary" },
  failed: { label: "Failed", dot: "bg-danger", text: "text-danger" },
};

export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  const meta = STATUS_META[status];
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-hairline bg-surface/60 px-2 py-0.5 text-2xs font-medium">
      <span className={cn("h-1.5 w-1.5 rounded-full", meta.dot, meta.pulse && "animate-pulse")} />
      <span className={meta.text}>{meta.label}</span>
    </span>
  );
}
