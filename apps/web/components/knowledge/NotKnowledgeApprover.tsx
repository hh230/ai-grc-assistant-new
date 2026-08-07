import { getTranslations } from "next-intl/server";
import { ShieldOff } from "lucide-react";
import { Card } from "@/components/ui/Card";

/**
 * Shown instead of the console to anyone who does not govern sector knowledge.
 *
 * States what the authority is rather than pretending the page does not exist: this is an internal
 * tool, and a colleague who lands here needs to know it is not theirs to operate, not that they
 * mistyped a URL.
 */
export async function NotKnowledgeApprover() {
  const t = await getTranslations("knowledgeConsole");
  return (
    <div className="mx-auto max-w-2xl">
      <Card grain>
        <div className="flex gap-3 py-2">
          <ShieldOff className="mt-0.5 h-4 w-4 shrink-0 text-foreground-muted" strokeWidth={1.75} />
          <div>
            <p className="text-sm font-medium text-foreground">{t("forbidden.title")}</p>
            <p className="mt-1 text-sm text-foreground-secondary">{t("forbidden.description")}</p>
          </div>
        </div>
      </Card>
    </div>
  );
}
