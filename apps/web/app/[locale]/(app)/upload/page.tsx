import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { can } from "@/lib/auth/permissions";
import { requireSession } from "@/lib/auth/server";
import { UploadCenter } from "@/components/upload/UploadCenter";

export const metadata: Metadata = {
  title: "Upload Center · Sentinel GRC",
};

export default async function UploadCenterPage() {
  const session = await requireSession();
  const t = await getTranslations("uploadPage");
  const canUpload = can(session.roles, "create", "knowledge_source");
  const canDelete = can(session.roles, "delete", "knowledge_source");

  return (
    <div>
      <header className="pb-7">
        <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          {t("eyebrow")}
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
          {t("title")}
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-foreground-secondary">{t("description")}</p>
      </header>

      <UploadCenter canUpload={canUpload} canDelete={canDelete} />
    </div>
  );
}
