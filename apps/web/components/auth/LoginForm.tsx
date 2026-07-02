"use client";

import { useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowRight, Loader2, Lock, Mail, ShieldHalf, TriangleAlert } from "lucide-react";
import { useRouter } from "@/i18n/navigation";
import { DEFAULT_AUTHENTICATED_PATH } from "@/lib/auth/config";

/** Restrict post-login redirects to in-app paths to prevent open-redirect abuse. */
function safeNext(raw: string | null): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return DEFAULT_AUTHENTICATED_PATH;
  return raw;
}

const DEMO_ACCOUNTS = [
  { email: "owner@acme.test", role: "Owner" },
  { email: "compliance@acme.test", role: "Compliance Manager" },
  { email: "analyst@acme.test", role: "Analyst" },
  { email: "viewer@acme.test", role: "Viewer" },
];

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = safeNext(searchParams.get("next"));

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) {
        const data = (await response.json().catch(() => ({}))) as { error?: string };
        setError(data.error ?? "Sign in failed. Please try again.");
        setIsSubmitting(false);
        return;
      }
      // Full navigation so the edge middleware sees the new cookie immediately.
      window.location.assign(next);
    } catch {
      setError("Network error. Please check your connection and try again.");
      setIsSubmitting(false);
    }
  }

  function fillDemo(demoEmail: string) {
    setEmail(demoEmail);
    setPassword("GrcDemo!2026");
    setError(null);
  }

  return (
    <div className="w-full max-w-sm">
      <div className="mb-8 flex flex-col items-center text-center">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2 shadow-soft">
          <ShieldHalf className="h-6 w-6 text-accent-foreground" strokeWidth={1.75} />
        </div>
        <h1 className="mt-4 text-xl font-semibold tracking-tight text-foreground">
          Sign in to Sentinel GRC
        </h1>
        <p className="mt-1 text-sm text-foreground-secondary">
          Governance · Risk · Compliance · AI
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {error && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-soft px-3 py-2.5 text-sm text-foreground"
          >
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-danger" strokeWidth={1.75} />
            <span>{error}</span>
          </div>
        )}

        <label className="block">
          <span className="mb-1.5 block text-xs font-medium text-foreground-secondary">
            Work email
          </span>
          <span className="relative block">
            <Mail
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground-muted"
              strokeWidth={1.75}
            />
            <input
              type="email"
              name="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              className="h-10 w-full rounded-lg border border-hairline bg-surface/60 pl-9 pr-3 text-sm text-foreground outline-none transition-colors duration-150 placeholder:text-foreground-muted focus:border-hairline-strong focus:bg-surface-2"
            />
          </span>
        </label>

        <label className="block">
          <span className="mb-1.5 block text-xs font-medium text-foreground-secondary">
            Password
          </span>
          <span className="relative block">
            <Lock
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground-muted"
              strokeWidth={1.75}
            />
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="h-10 w-full rounded-lg border border-hairline bg-surface/60 pl-9 pr-3 text-sm text-foreground outline-none transition-colors duration-150 placeholder:text-foreground-muted focus:border-hairline-strong focus:bg-surface-2"
            />
          </span>
        </label>

        <button
          type="submit"
          disabled={isSubmitting}
          className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-accent text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
              Signing in…
            </>
          ) : (
            <>
              Sign in
              <ArrowRight className="h-4 w-4" strokeWidth={2} />
            </>
          )}
        </button>
      </form>

      <div className="mt-7 rounded-xl border border-hairline bg-surface/40 p-4">
        <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          Demo accounts
        </p>
        <p className="mt-1 text-xs text-foreground-muted">
          Click to fill. Password:{" "}
          <span className="font-mono text-foreground-secondary">GrcDemo!2026</span>
        </p>
        <div className="mt-2.5 grid grid-cols-2 gap-1.5">
          {DEMO_ACCOUNTS.map((account) => (
            <button
              key={account.email}
              type="button"
              onClick={() => fillDemo(account.email)}
              className="rounded-lg border border-hairline bg-surface/60 px-2.5 py-1.5 text-left transition-colors duration-150 hover:border-hairline-strong hover:bg-surface-2"
            >
              <span className="block truncate text-xs text-foreground">{account.role}</span>
              <span className="block truncate text-2xs text-foreground-muted">{account.email}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
