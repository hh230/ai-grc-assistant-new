import type { Metadata } from "next";
import { ArrowLeft, ShieldX } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { Card } from "@/components/ui/Card";

export const metadata: Metadata = {
  title: "Access denied",
};

export default function AccessDeniedPage() {
  return (
    <Card
      grain
      className="mx-auto mt-10 flex max-w-md flex-col items-center gap-4 py-14 text-center"
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-danger/30 bg-danger-soft">
        <ShieldX className="h-5 w-5 text-danger" strokeWidth={1.75} />
      </div>
      <div className="space-y-1.5">
        <h1 className="text-base font-semibold tracking-tight text-foreground">Access denied</h1>
        <p className="max-w-xs text-xs text-foreground-muted">
          Your role does not grant access to this area. If you believe this is a mistake, contact
          your workspace administrator.
        </p>
      </div>
      <Link
        href="/dashboard"
        className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-hairline bg-surface/60 px-3 text-sm text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:bg-surface-2 hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" strokeWidth={1.75} />
        Back to dashboard
      </Link>
    </Card>
  );
}
