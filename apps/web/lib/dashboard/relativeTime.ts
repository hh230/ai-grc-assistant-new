import type { AppLocale } from "@/i18n/routing";

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 60 * 60],
  ["month", 30 * 24 * 60 * 60],
  ["week", 7 * 24 * 60 * 60],
  ["day", 24 * 60 * 60],
  ["hour", 60 * 60],
  ["minute", 60],
];

/** "2 hours ago" / "منذ ساعتين" — locale-correct via Intl, no per-string translation keys. */
export function formatRelativeTime(iso: string, locale: AppLocale): string {
  const diffSeconds = Math.round((new Date(iso).getTime() - Date.now()) / 1000);
  const formatter = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });

  for (const [unit, secondsInUnit] of UNITS) {
    const value = diffSeconds / secondsInUnit;
    if (Math.abs(value) >= 1) {
      return formatter.format(Math.round(value), unit);
    }
  }
  return formatter.format(Math.round(diffSeconds / 60) || 0, "minute");
}
