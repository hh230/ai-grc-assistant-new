import type { ReactNode } from "react";
import { SessionProvider } from "@/components/auth/SessionProvider";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { AppShell } from "@/components/layout/AppShell";
import { requireSession } from "@/lib/auth/server";
import { toSessionUser } from "@/lib/auth/types";
import { isKnowledgeApprover } from "@/lib/knowledge/service";

/**
 * Layout for every authenticated workspace route. Enforces the session server-side
 * (defense-in-depth behind the edge middleware) and provides the public identity and the
 * server-state cache to the client tree, then renders the persistent app shell.
 */
export default async function AuthenticatedLayout({ children }: { children: ReactNode }) {
  const session = await requireSession();
  // Resolved here, server-side, because it comes from configuration rather than from the session
  // cookie — a client must never be able to assert it.
  const user = {
    ...toSessionUser(session),
    governsKnowledge: isKnowledgeApprover({ userEmail: session.email }),
  };
  return (
    <SessionProvider user={user}>
      <QueryProvider>
        <AppShell>{children}</AppShell>
      </QueryProvider>
    </SessionProvider>
  );
}
