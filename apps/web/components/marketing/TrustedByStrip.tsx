"use client";

import { Rocket, Building, Building2, Landmark, HeartHandshake } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

/**
 * Pre-launch credibility strip (V2-P3 design proposal §7): no real customer logos exist
 * yet, so this launches as sector/credibility framing instead — swap to real customer
 * logos (same visual treatment) once available. Organization-size framing (V2.5 Rasheed
 * brand transition) rather than industry-sector framing.
 */
const SECTOR_ICONS = [
  { key: "startups", icon: Rocket },
  { key: "midSize", icon: Building },
  { key: "enterprise", icon: Building2 },
  { key: "government", icon: Landmark },
  { key: "nonprofit", icon: HeartHandshake },
] as const;

interface TrustedByStripProps {
  label: string;
  className?: string;
}

export function TrustedByStrip({ label, className }: TrustedByStripProps) {
  const t = useTranslations("home.trustedBy");

  return (
    <div className={cn("text-center", className)}>
      <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
        {label}
      </p>
      <div className="mt-4 flex flex-wrap items-center justify-center gap-3">
        {SECTOR_ICONS.map((sector) => (
          <span
            key={sector.key}
            className="inline-flex items-center gap-2 rounded-full border border-hairline bg-surface px-4 py-2 text-xs font-medium text-foreground-secondary opacity-80"
          >
            <sector.icon className="h-3.5 w-3.5 text-foreground-muted" strokeWidth={1.75} />
            {t(sector.key)}
          </span>
        ))}
      </div>
    </div>
  );
}
