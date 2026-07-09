import { z } from "zod";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { checkRateLimit } from "@/lib/auth/rate-limit";
import { ValidationError } from "@/lib/errors";
import { AiProviderError, getChatProvider } from "@/lib/ai";
import { finalizeTurn, prepareTurn } from "@/lib/chat/service";
import { logger } from "@/lib/observability/logger";

export const runtime = "nodejs";
// A full grounded gpt-5 turn (retrieval + reasoning + a long streamed answer) can take a
// few minutes; without this the platform's default duration can kill the function
// mid-stream, truncating the NDJSON stream with no terminating event.
export const maxDuration = 300;

const chatSchema = z.object({
  conversationId: z.string().nullish(),
  message: z.string().trim().min(1).max(8000),
});

// This is the app's main LLM-cost/abuse surface: unlike the analysis pipeline (which has a
// per-user daily quota), chat has no business-level cap, so both a per-user and a coarser
// per-tenant window guard against one user or one tenant driving unbounded model spend.
const USER_WINDOW_MS = 5 * 60_000;
const USER_MAX_MESSAGES = 20;
const TENANT_WINDOW_MS = 5 * 60_000;
const TENANT_MAX_MESSAGES = 100;

/**
 * RAG chat. Retrieves grounding, then streams the assistant answer as newline-delimited
 * JSON events: a `meta` event (conversationId + citations), many `delta` events, then `done`.
 * Errors before streaming are returned as JSON; errors mid-stream become a `done`-terminating
 * `error` event.
 */
export async function POST(request: Request): Promise<Response> {
  const actor = await getActor();
  if (!actor) return unauthorized();

  const userLimit = await checkRateLimit(`chat:user:${actor.userId}`, {
    windowMs: USER_WINDOW_MS,
    maxAttempts: USER_MAX_MESSAGES,
  });
  const tenantLimit = userLimit.allowed
    ? await checkRateLimit(`chat:tenant:${actor.tenantId}`, {
        windowMs: TENANT_WINDOW_MS,
        maxAttempts: TENANT_MAX_MESSAGES,
      })
    : userLimit;
  if (!userLimit.allowed || !tenantLimit.allowed) {
    const retryAfterSeconds = Math.max(userLimit.retryAfterSeconds, tenantLimit.retryAfterSeconds);
    return new Response(
      JSON.stringify({ error: "Too many messages. Please try again shortly." }),
      {
        status: 429,
        headers: {
          "Content-Type": "application/json",
          "Retry-After": String(retryAfterSeconds),
        },
      },
    );
  }

  let prepared;
  try {
    const body = await request.json().catch(() => null);
    const parsed = chatSchema.safeParse(body);
    if (!parsed.success) throw new ValidationError("A non-empty message is required.");
    prepared = await prepareTurn(actor, parsed.data.conversationId ?? null, parsed.data.message);
  } catch (error) {
    return errorResponse(error);
  }

  const { conversation, citations, llmMessages } = prepared;
  const encoder = new TextEncoder();

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      let closed = false;
      const send = (event: unknown) => {
        if (closed) return;
        try {
          controller.enqueue(encoder.encode(`${JSON.stringify(event)}\n`));
        } catch {
          // The consumer disconnected (tab closed, connection dropped) — stop writing.
          closed = true;
        }
      };
      // gpt-5 is a reasoning model: after `meta` it can go 30s+ without emitting a single
      // token. Idle-timeout proxies kill exactly that kind of silent stream, truncating it
      // with no terminating event — periodic pings keep bytes flowing until real deltas
      // arrive. The client ignores unknown event types.
      const keepAlive = setInterval(() => send({ type: "ping" }), 15_000);
      try {
        send({
          type: "meta",
          conversationId: conversation.id,
          title: conversation.title,
          citations,
        });

        const chat = getChatProvider();
        let full = "";
        if (chat.stream) {
          await chat.stream(
            llmMessages,
            (delta) => {
              full += delta;
              send({ type: "delta", text: delta });
            },
            { maxTokens: 16000 },
          );
        } else {
          full = await chat.complete(llmMessages, { maxTokens: 16000 });
          send({ type: "delta", text: full });
        }

        await finalizeTurn(actor, conversation.id, full, citations);
        send({ type: "done" });
      } catch (error) {
        // Full detail (including any raw upstream AI-provider response body) goes to
        // server logs only. `AiProviderError` messages can echo upstream text and must
        // never reach a user; send an empty string so the client renders its own
        // localized, Arabic-aware fallback copy instead of an internal error string.
        logger.error("chat_stream_failed", error, { conversationId: conversation.id });
        send({
          type: "error",
          error:
            error instanceof AiProviderError
              ? ""
              : error instanceof Error
                ? error.message
                : "The assistant failed to respond.",
        });
      } finally {
        clearInterval(keepAlive);
        closed = true;
        try {
          controller.close();
        } catch {
          // Already cancelled by the consumer.
        }
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "application/x-ndjson; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Accel-Buffering": "no",
    },
  });
}
