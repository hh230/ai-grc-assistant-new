import type { ReactNode } from "react";
import { SessionProvider } from "@/components/auth/SessionProvider";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { AppShell } from "@/components/layout/AppShell";
import { requireSession } from "@/lib/auth/server";
import { toSessionUser } from "@/lib/auth/types";

/**
 * Layout for every authenticated workspace route. Enforces the session server-side
 * (defense-in-depth behind the edge middleware) and provides the public identity and the
 * server-state cache to the client tree, then renders the persistent app shell.
 */
export default async function AuthenticatedLayout({ children }: { children: ReactNode }) {
  const session = await requireSession();
  return (
    <SessionProvider user={toSessionUser(session)}>
      <QueryProvider>
        <AppShell>{children}</AppShell>
      </QueryProvider>
    </SessionProvider>
  );
}
