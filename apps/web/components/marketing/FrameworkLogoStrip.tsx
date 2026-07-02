import { Library } from "lucide-react";
import { cn } from "@/lib/utils";

export interface MarketingFramework {
  shortName: string;
  name: string;
  region: string;
  description?: string;
}

export const SUPPORTED_FRAMEWORKS: MarketingFramework[] = [
  {
    shortName: "NCA ECC",
    name: "Essential Cybersecurity Controls",
    region: "Saudi Arabia",
    description: "The National Cybersecurity Authority's baseline cybersecurity controls.",
  },
  {
    shortName: "SAMA",
    name: "SAMA Cybersecurity Framework",
    region: "Saudi Arabia",
    description: "Saudi Central Bank cybersecurity and compliance requirements for the financial sector.",
  },
  {
    shortName: "PDPL",
    name: "Personal Data Protection Law",
    region: "Saudi Arabia",
    description: "Saudi Arabia's personal data protection and privacy regulation.",
  },
  {
    shortName: "ISO 27001",
    name: "ISO/IEC 27001:2022",
    region: "International",
    description: "The international standard for information security management systems.",
  },
  {
    shortName: "NIST CSF",
    name: "NIST Cybersecurity Framework",
    region: "International",
    description: "A risk-based framework for managing cybersecurity outcomes.",
  },
  {
    shortName: "CIS Controls",
    name: "CIS Critical Security Controls",
    region: "International",
    description: "Prioritized safeguards to mitigate the most common cyber attacks.",
  },
  {
    shortName: "COBIT",
    name: "COBIT",
    region: "International",
    description: "Governance and management framework for enterprise IT.",
  },
  {
    shortName: "COSO",
    name: "COSO Internal Control Framework",
    region: "International",
    description: "Internal control and enterprise risk management framework.",
  },
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
