import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { listConversations } from "@/lib/chat/service";
import { toConversationSummary } from "@/lib/chat/types";

export const runtime = "nodejs";

export async function GET(): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const conversations = await listConversations(actor);
    return NextResponse.json({ conversations: conversations.map(toConversationSummary) });
  } catch (error) {
    return errorResponse(error);
  }
}
