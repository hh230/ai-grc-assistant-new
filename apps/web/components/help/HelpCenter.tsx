import { Mail, HelpCircle, Upload, Users, Library } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { Card } from "@/components/ui/Card";
import { Link } from "@/i18n/navigation";

const SUPPORT_EMAIL = "m.alsayyar@outlook.sa";

const GETTING_STARTED = [
  { icon: Upload, key: "upload", href: "/upload" },
  { icon: Users, key: "invite", href: "/settings" },
  { icon: Library, key: "frameworks", href: "/frameworks" },
] as const;

export async function HelpCenter() {
  const t = await getTranslations("helpPage");

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Card className="flex flex-col items-center gap-3 py-8 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2 shadow-soft">
            <Mail className="h-5 w-5 text-accent" strokeWidth={1.75} />
          </div>
          <p className="text-sm font-medium text-foreground">{t("contact.title")}</p>
          <p className="max-w-xs text-xs text-foreground-muted">{t("contact.description")}</p>
          <a
            href={`mailto:${SUPPORT_EMAIL}`}
            className="text-sm font-medium text-accent-foreground hover:underline"
            dir="ltr"
          >
            {SUPPORT_EMAIL}
          </a>
        </Card>

        <Card className="flex flex-col items-center gap-3 py-8 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2 shadow-soft">
            <HelpCircle className="h-5 w-5 text-accent" strokeWidth={1.75} />
          </div>
          <p className="text-sm font-medium text-foreground">{t("faq.title")}</p>
          <p className="max-w-xs text-xs text-foreground-muted">{t("faq.description")}</p>
          <Link href="/faq" className="text-sm font-medium text-accent-foreground hover:underline">
            {t("faq.cta")}
          </Link>
        </Card>
      </div>

      <Card>
        <p className="text-sm font-semibold text-foreground">{t("gettingStarted.title")}</p>
        <div className="mt-4 space-y-1">
          {GETTING_STARTED.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.key}
                href={item.href}
                className="flex items-center gap-3 rounded-lg px-2.5 py-2.5 text-sm transition-colors duration-150 hover:bg-white/[0.03]"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent-foreground">
                  <Icon className="h-4 w-4" strokeWidth={1.75} />
                </span>
                <span className="text-foreground-secondary">
                  {t(`gettingStarted.${item.key}`)}
                </span>
              </Link>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
