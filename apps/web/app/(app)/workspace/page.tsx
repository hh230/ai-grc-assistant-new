import type { Metadata } from "next";
import { requireSession } from "@/lib/auth/server";
import { ChatWorkspace } from "@/components/chat/ChatWorkspace";

export const metadata: Metadata = {
  title: "AI Workspace · Sentinel GRC",
};

export default async function WorkspacePage() {
  // The AI assistant is available to any authenticated member (read access to knowledge).
  await requireSession();
  return (
    <div>
      <header className="pb-5">
        <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          Overview
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">AI Workspace</h1>
        <p className="mt-1 max-w-2xl text-sm text-foreground-secondary">
          Chat with your GRC knowledge base. Answers are retrieved from your tenant’s indexed
          documents and cite their sources.
        </p>
      </header>

      <ChatWorkspace />
    </div>
  );
}
