import { Library } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * `shortName` is the framework's internationally recognized code — never translated (CLAUDE.md
 * §21 "Frameworks are referenced by stable identifiers"). `key` looks up the translated full
 * name/description/region in the `marketingFrameworks` message namespace; `regionKey` drives
 * locale-invariant logic (e.g. badge tone) since the display region text is translated.
 */
export interface MarketingFramework {
  key: string;
  shortName: string;
  regionKey: "ksa" | "international";
}

export const SUPPORTED_FRAMEWORKS: MarketingFramework[] = [
  { key: "ncaEcc", shortName: "NCA ECC", regionKey: "ksa" },
  { key: "sama", shortName: "SAMA", regionKey: "ksa" },
  { key: "pdpl", shortName: "PDPL", regionKey: "ksa" },
  { key: "iso27001", shortName: "ISO 27001", regionKey: "international" },
  { key: "nistCsf", shortName: "NIST CSF", regionKey: "international" },
  { key: "cisControls", shortName: "CIS Controls", regionKey: "international" },
  { key: "cobit", shortName: "COBIT", regionKey: "international" },
  { key: "coso", shortName: "COSO", regionKey: "international" },
];

interface FrameworkLogoStripProps {
  className?: string;
}

/** Compact trust strip (Home) — shortName pills only. */
export function FrameworkLogoStrip({ className }: FrameworkLogoStripProps) {
  return (
    <div className={cn("flex flex-wrap items-center justify-center gap-3", className)}>
      {SUPPORTED_FRAMEWORKS.map((fw) => (
        <span
          key={fw.shortName}
          className="inline-flex items-center gap-1.5 rounded-full border border-hairline bg-surface px-3.5 py-1.5 text-xs font-medium text-foreground-secondary shadow-soft"
        >
          <Library className="h-3.5 w-3.5 text-foreground-muted" strokeWidth={1.75} />
          {fw.shortName}
        </span>
      ))}
    </div>
  );
}
