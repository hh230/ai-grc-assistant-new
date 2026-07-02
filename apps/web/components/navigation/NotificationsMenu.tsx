"use client";

import { Bell } from "lucide-react";
import { useTranslations } from "next-intl";
import { Popover } from "@/components/ui/Popover";
import { NOTIFICATIONS } from "@/lib/data";
import { cn } from "@/lib/utils";

const dotTone: Record<string, string> = {
  danger: "bg-danger",
  accent: "bg-accent",
  neutral: "bg-foreground-muted",
};

export function NotificationsMenu() {
  const unread = NOTIFICATIONS.filter((n) => n.unread).length;
  const t = useTranslations("notifications");

  return (
    <Popover
      width={332}
      ariaLabel={unread > 0 ? t("menuLabelUnread", { count: unread }) : t("menuLabel")}
      trigger={() => (
        <span className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-hairline bg-surface/60 text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:bg-surface-2 hover:text-foreground">
          <Bell className="h-4 w-4" strokeWidth={1.75} />
          {unread > 0 && (
            <span className="absolute end-2 top-2 h-1.5 w-1.5 rounded-full bg-danger ring-2 ring-canvas" />
          )}
        </span>
      )}
    >
      <div className="flex items-center justify-between border-b border-hairline px-4 py-3">
        <p className="text-sm font-semibold text-foreground">{t("title")}</p>
        <span className="text-2xs text-foreground-muted">{t("unread", { count: unread })}</span>
      </div>
      <div className="max-h-80 overflow-y-auto py-1">
        {NOTIFICATIONS.map((n) => (
          <button
            key={n.id}
            type="button"
            className="flex w-full items-start gap-3 px-4 py-3 text-start transition-colors duration-150 hover:bg-white/[0.03]"
          >
            <span className={cn("mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full", dotTone[n.tone])} />
            <span className="min-w-0 flex-1">
              <span className="block text-xs font-medium text-foreground">{n.title}</span>
              <span className="mt-0.5 block truncate text-2xs text-foreground-muted">
                {n.detail}
              </span>
            </span>
            <span className="shrink-0 text-2xs text-foreground-muted">{n.time}</span>
          </button>
        ))}
      </div>
      <div className="border-t border-hairline px-4 py-2.5">
        <button
          type="button"
          className="text-2xs font-medium text-accent-foreground hover:underline"
        >
          {t("viewAll")}
        </button>
      </div>
    </Popover>
  );
}
