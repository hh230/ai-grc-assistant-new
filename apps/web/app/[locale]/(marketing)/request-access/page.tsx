import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { Hero } from "@/components/marketing/Hero";
import { Card } from "@/components/ui/Card";
import { RequestAccessForm } from "@/components/accessRequests/RequestAccessForm";

export const metadata: Metadata = {
  title: "Request Access · Rasheed",
  description: "Request access to the Rasheed governance, risk, compliance and AI platform.",
};

export default async function RequestAccessPage() {
  const t = await getTranslations("requestAccessPage");

  return (
    <>
      <Hero title={t("hero.title")} description={t("hero.description")} />

      <section className="mx-auto max-w-[560px] px-4 pb-20 sm:px-6">
        <Card className="p-6 sm:p-8">
          <RequestAccessForm />
        </Card>
      </section>
    </>
  );
}
