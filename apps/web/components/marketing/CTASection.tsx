import type { Route } from "next";
import { ArrowRight } from "lucide-react";
import { Link } from "@/i18n/navigation";

interface CTASectionProps {
  title: string;
  description: string;
  ctaLabel?: string;
  ctaHref?: Route;
}

export function CTASection({
  title,
  description,
  ctaLabel = "Get started",
  ctaHref = "/login" as Route,
}: CTASectionProps) {
  return (
    <section className="border-t border-hairline bg-canvas">
      <div className="mx-auto max-w-[720px] px-4 py-20 text-center sm:px-6">
        <h2 className="text-balance text-3xl font-semibold tracking-tight text-foreground">
          {title}
        </h2>
        <p className="text-balance mx-auto mt-4 max-w-[520px] text-base leading-relaxed text-foreground-secondary">
          {description}
        </p>
        <Link
          href={ctaHref}
          className="mt-8 inline-flex h-11 items-center gap-1.5 rounded-lg bg-accent px-5 text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90"
        >
          {ctaLabel}
          <ArrowRight className="h-4 w-4 flip-rtl" strokeWidth={1.75} />
        </Link>
      </div>
    </section>
  );
}
