import type { LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/Card";

interface PlaceholderPageProps {
  /** Small uppercase group label shown above the title (e.g. "Governance"). */
  eyebrow: string;
  title: string;
  description: string;
  icon: LucideIcon;
}

/**
 * Standard empty-state page for the P1 dashboard shell. Every navigation
 * destination that does not yet have a built experience renders one of these so
 * the shell feels complete and navigable while signalling that functionality is
 * intentionally deferred to a later roadmap phase.
 */
export function PlaceholderPage({ eyebrow, title, description, icon: Icon }: PlaceholderPageProps) {
  return (
    <div>
      <div className="pb-7">
        <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          {eyebrow}
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
        <p className="mt-1 max-w-xl text-sm text-foreground-secondary">{description}</p>
      </div>

      <Card grain className="flex flex-col items-center justify-center gap-4 py-16 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2 shadow-soft">
          <Icon className="h-5 w-5 text-accent-foreground" strokeWidth={1.75} />
        </div>
        <div className="max-w-sm space-y-1.5">
          <p className="text-sm font-medium text-foreground">This workspace is coming soon</p>
          <p className="text-xs text-foreground-muted">
            The {title} module is part of the product roadmap. The navigation, layout, and shell are
            in place — functionality arrives in a later phase.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-hairline bg-surface/60 px-2.5 py-1 text-2xs font-medium text-foreground-muted">
          <span className="h-1.5 w-1.5 rounded-full bg-warning" />
          Placeholder · P1 shell
        </span>
      </Card>
    </div>
  );
}
