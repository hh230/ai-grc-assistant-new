import { NextResponse } from "next/server";
import { errorResponse } from "@/lib/api/respond";
import { previewInvitation } from "@/lib/invitations/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ token: string }>;
}

/** Public: preview an invitation (email/organization/role/expiry) so the accept-invite page
 * can render before the visitor sets a password. Rejects used/expired/unknown tokens. */
export async function GET(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const { token } = await params;
    const preview = await previewInvitation(token);
    return NextResponse.json({ invitation: preview });
  } catch (error) {
    return errorResponse(error);
  }
}
