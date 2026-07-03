import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { getRequestLocale } from "@/lib/i18n/request-locale";
import { buildReport } from "@/lib/reports/service";
import { REPORT_KINDS, type ReportKind } from "@/lib/reports/types";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ kind: string }>;
}

export async function GET(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { kind } = await params;
    if (!(REPORT_KINDS as readonly string[]).includes(kind)) {
      throw new ValidationError("Unknown report type.");
    }
    const locale = await getRequestLocale();
    const report = await buildReport(actor, kind as ReportKind, locale);
    return NextResponse.json({ report });
  } catch (error) {
    return errorResponse(error);
  }
}
