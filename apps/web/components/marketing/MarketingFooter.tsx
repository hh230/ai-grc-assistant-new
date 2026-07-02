import type { Route } from "next";
import { ShieldHalf } from "lucide-react";
import { Link } from "@/i18n/navigation";

const COLUMNS: { title: string; links: { label: string; href: Route }[] }[] = [
  {
    title: "Product",
    links: [
      { label: "Overview", href: "/product" },
      { label: "Features", href: "/features" },
      { label: "How it works", href: "/how-it-works" },
    ],
  },
  {
    title: "Compliance",
    links: [
      { label: "Frameworks supported", href: "/frameworks-supported" },
      { label: "Example reports", href: "/sample-reports" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "FAQ", href: "/faq" },
      { label: "Sign in", href: "/login" },
    ],
  },
];

export function MarketingFooter() {
  return (
    <footer className="border-t border-hairline bg-canvas">
      <div className="mx-auto max-w-[1200px] px-4 py-14 sm:px-6">
        <div className="grid grid-cols-2 gap-10 sm:grid-cols-4">
          <div className="col-span-2 sm:col-span-1">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-hairline-strong bg-surface shadow-soft">
                <ShieldHalf className="h-[18px] w-[18px] text-accent" strokeWidth={1.75} />
              </div>
              <span className="text-sm font-semibold tracking-tight text-foreground">
                Sentinel GRC
              </span>
            </div>
            <p className="mt-3 max-w-[220px] text-xs text-foreground-muted">
              Governance, Risk, and Compliance — grounded, cited, and audit-ready.
            </p>
          </div>

          {COLUMNS.map((column) => (
            <div key={column.title}>
              <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
                {column.title}
              </p>
              <ul className="mt-3 space-y-2">
                {column.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-sm text-foreground-secondary transition-colors duration-150 hover:text-foreground"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 border-t border-hairline pt-6">
          <p className="text-2xs text-foreground-muted">
            © {new Date().getFullYear()} Sentinel GRC · Enterprise Edition
          </p>
        </div>
      </div>
    </footer>
  );
}
