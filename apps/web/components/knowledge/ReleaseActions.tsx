"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";
import { actOnRelease, setActiveRelease } from "@/lib/knowledge/client";
import type { KnowledgeRelease, ReleaseAction } from "@/lib/knowledge/types";

/**
 * The lifecycle gate, as a reviewer operates it.
 *
 * Only the transitions valid from the current status are offered — but the button set is a
 * *convenience*, not the rule. The rule is the guarded `WHERE` clause behind each write, and a
 * transition that is no longer valid returns `changed: false`, which this reports as "nothing
 * changed" rather than as a failure. That is what makes a double-click harmless.
 *
 * Publishing and activating are deliberately two buttons. Publishing makes a release eligible;
 * activating decides which one customers actually see. Collapsing them would remove the state in
 * which a release is ready and a human has not yet decided to serve it.
 */
export function ReleaseActions({
  release,
  isLive,
}: {
  release: KnowledgeRelease;
  isLive: boolean;
}) {
  const t = useTranslations("knowledgeConsole");
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ tone: "ok" | "idle" | "error"; text: string } | null>(
    null,
  );
  const [reason, setReason] = useState("");
  const [, startTransition] = useTransition();

  async function run(key: string, action: () => Promise<{ changed: boolean }>) {
    setBusy(key);
    setMessage(null);
    try {
      const outcome = await action();
      setMessage(
        outcome.changed
          ? { tone: "ok", text: t("actions.done") }
          : // Not an error: every knowledge write is idempotent, so the release was simply
            // already past this point — usually because someone else moved it.
            { tone: "idle", text: t("actions.alreadyDone") },
      );
      startTransition(() => router.refresh());
    } catch (cause) {
      setMessage({ tone: "error", text: cause instanceof Error ? cause.message : String(cause) });
    } finally {
      setBusy(null);
    }
  }

  const transitions: ReleaseAction[] =
    release.status === "draft"
      ? ["submit"]
      : release.status === "in_review"
        ? ["approve", "reject"]
        : release.status === "approved"
          ? ["publish", "reject"]
          : [];

  const canActivate = release.status === "released" && !isLive;

  return (
    <div className="space-y-2.5">
      <div className="flex flex-wrap items-center gap-2">
        {transitions.map((action) => (
          <button
            key={action}
            type="button"
            disabled={busy !== null}
            onClick={() => void run(action, () => actOnRelease(release.id, action))}
            className={
              action === "reject"
                ? "inline-flex h-8 items-center gap-1.5 rounded-lg border border-hairline px-3 text-2xs font-medium text-foreground-secondary hover:text-foreground disabled:opacity-60"
                : "inline-flex h-8 items-center gap-1.5 rounded-lg bg-accent px-3 text-2xs font-medium text-white shadow-glow hover:opacity-90 disabled:opacity-60"
            }
          >
            {busy === action && <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2} />}
            {t(`actions.${action}`)}
          </button>
        ))}

        {isLive && (
          <span className="rounded-md bg-accent-soft px-2 py-1 text-2xs font-medium text-accent-foreground">
            {t("actions.isLive")}
          </span>
        )}
      </div>

      {canActivate && (
        <form
          className="flex flex-wrap items-end gap-2 rounded-lg border border-hairline bg-surface px-3 py-2.5"
          onSubmit={(event) => {
            event.preventDefault();
            void run("activate", () =>
              setActiveRelease(release.industrySlug, release.id, reason.trim()),
            );
          }}
        >
          <label className="flex min-w-[14rem] flex-1 flex-col gap-1 text-2xs text-foreground-muted">
            {/* Required, because a rollback and a routine upgrade are the same call and read
                identically in the history without it. */}
            {t("actions.reasonLabel")}
            <input
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              required
              placeholder={t("actions.reasonPlaceholder")}
              className="h-8 rounded-lg border border-hairline bg-surface-elevated px-2 text-sm text-foreground"
            />
          </label>
          <button
            type="submit"
            disabled={busy !== null}
            className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-accent px-3 text-2xs font-medium text-white shadow-glow hover:opacity-90 disabled:opacity-60"
          >
            {busy === "activate" && <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2} />}
            {t("actions.activate")}
          </button>
        </form>
      )}

      {message && (
        <p
          className={
            message.tone === "error"
              ? "text-2xs text-danger"
              : message.tone === "ok"
                ? "text-2xs text-foreground-secondary"
                : "text-2xs text-foreground-muted"
          }
        >
          {message.text}
        </p>
      )}
    </div>
  );
}
