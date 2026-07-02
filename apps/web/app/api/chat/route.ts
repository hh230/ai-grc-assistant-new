import { z } from "zod";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { getChatProvider } from "@/lib/ai";
import { finalizeTurn, prepareTurn } from "@/lib/chat/service";

export const runtime = "nodejs";

const chatSchema = z.object({
  conversationId: z.string().nullish(),
  message: z.string().trim().min(1).max(8000),
});

/**
 * RAG chat. Retrieves grounding, then streams the assistant answer as newline-delimited
 * JSON events: a `meta` event (conversationId + citations), many `delta` events, then `done`.
 * Errors before streaming are returned as JSON; errors mid-stream become a `done`-terminating
 * `error` event.
 */
export async function POST(request: Request): Promise<Response> {
  const actor = await getActor();
  if (!actor) return unauthorized();

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
      const send = (event: unknown) =>
        controller.enqueue(encoder.encode(`${JSON.stringify(event)}\n`));
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
        send({
          type: "error",
          error: error instanceof Error ? error.message : "The assistant failed to respond.",
        });
      } finally {
        controller.close();
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
