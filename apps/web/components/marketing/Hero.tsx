import type { ReactNode } from "react";
import { ArrowRight } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/utils";

interface HeroProps {
  eyebrow?: string;
  title: string;
  /** Optional short tagline rendered between the title and the description. */
  subtitle?: string;
  description: string;
  // Locale-agnostic logical path — see the comment on NavLink.href in lib/navigation.ts.
  primaryCta?: { label: string; href: string };
  secondaryCta?: { label: string; href: string };
  children?: ReactNode;
  className?: string;
}

export function Hero({
  eyebrow,
  title,
  subtitle,
  description,
  primaryCta,
  secondaryCta,
  children,
  className,
}: HeroProps) {
  return (
    <section className={cn("relative overflow-hidden bg-canvas", className)}>
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-96 bg-accent-fade"
        aria-hidden
      />
      <div className="relative mx-auto max-w-[860px] px-4 py-20 text-center sm:px-6 sm:py-28">
        {eyebrow && (
          <span className="inline-flex items-center rounded-full border border-gold/30 bg-gold-soft px-3 py-1 text-2xs font-medium text-accent">
            {eyebrow}
          </span>
        )}
        <h1 className="text-balance mt-5 text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
          {title}
        </h1>
        {subtitle && (
          <p className="text-balance mx-auto mt-3 max-w-[620px] text-lg font-medium text-foreground-secondary sm:text-xl">
            {subtitle}
          </p>
        )}
        <p className="text-balance mx-auto mt-5 max-w-[620px] text-base leading-relaxed text-foreground-secondary sm:text-lg">
          {description}
        </p>

        {(primaryCta || secondaryCta) && (
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            {primaryCta && (
              <Link
                href={primaryCta.href}
                className="inline-flex h-11 items-center gap-1.5 rounded-lg bg-accent px-5 text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90 active:scale-[0.98]"
              >
                {primaryCta.label}
                <ArrowRight className="h-4 w-4 flip-rtl" strokeWidth={1.75} />
              </Link>
            )}
            {secondaryCta && (
              <Link
                href={secondaryCta.href}
                className="inline-flex h-11 items-center gap-1.5 rounded-lg border border-hairline bg-surface px-5 text-sm font-medium text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:text-foreground"
              >
                {secondaryCta.label}
              </Link>
            )}
          </div>
        )}

        {children}
      </div>
    </section>
  );
}
