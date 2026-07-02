import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { requireSession } from "@/lib/auth/server";
import { ChatWorkspace } from "@/components/chat/ChatWorkspace";

export const metadata: Metadata = {
  title: "AI Assistant · Sentinel GRC",
};

export default async function WorkspacePage() {
  // The AI assistant is available to any authenticated member (read access to knowledge).
  await requireSession();
  const t = await getTranslations("nav");
  const tAssistant = await getTranslations("aiAssistant");
  return (
    <div>
      <header className="pb-5">
        <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          {t("groups.overview")}
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
          {t("items.aiAssistant")}
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-foreground-secondary">
          {tAssistant("pageSubtitle")}
        </p>
      </header>

      <ChatWorkspace />
    </div>
  );
}
