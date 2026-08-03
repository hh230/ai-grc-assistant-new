"use client";

import { Bell } from "lucide-react";
import { useTranslations } from "next-intl";
import { Popover } from "@/components/ui/Popover";

/** No notification-generation system exists yet (post-v2.0.1 audit — this used to render a
 * hardcoded demo array with a permanent "2 unread" badge, misrepresenting every tenant's
 * account). Until real events (mission updates, approvals, findings) are wired to produce
 * notifications, this stays an honest empty state rather than fabricated activity. */
export function NotificationsMenu() {
  const t = useTranslations("notifications");

  return (
    <Popover
      width={332}
      ariaLabel={t("menuLabel")}
      trigger={() => (
        <span className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-hairline bg-surface/60 text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:bg-surface-2 hover:text-foreground">
          <Bell className="h-4 w-4" strokeWidth={1.75} />
        </span>
      )}
    >
      <div className="border-b border-hairline px-4 py-3">
        <p className="text-sm font-semibold text-foreground">{t("title")}</p>
      </div>
      <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
        <Bell className="h-5 w-5 text-foreground-muted" strokeWidth={1.75} />
        <p className="text-xs text-foreground-muted">{t("empty")}</p>
      </div>
    </Popover>
  );
}
