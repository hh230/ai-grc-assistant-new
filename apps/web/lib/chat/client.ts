/** Browser-side chat client, including the NDJSON streaming consumer for `/api/chat`. */

import type { Citation, Conversation, ConversationSummary } from "./types";

async function parseError(response: Response): Promise<string> {
  const data = (await response.json().catch(() => ({}))) as { error?: string };
  return data.error ?? `Request failed (${response.status}).`;
}

export async function fetchConversations(): Promise<ConversationSummary[]> {
  const response = await fetch("/api/conversations", { cache: "no-store" });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { conversations: ConversationSummary[] }).conversations;
}

export async function fetchConversation(id: string): Promise<Conversation> {
  const response = await fetch(`/api/conversations/${id}`, { cache: "no-store" });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { conversation: Conversation }).conversation;
}

export async function deleteConversation(id: string): Promise<void> {
  const response = await fetch(`/api/conversations/${id}`, { method: "DELETE" });
  if (!response.ok) throw new Error(await parseError(response));
}

export interface ChatMeta {
  conversationId: string;
  title: string;
  citations: Citation[];
}

export interface ChatStreamHandlers {
  onMeta: (meta: ChatMeta) => void;
  onDelta: (text: string) => void;
  onDone: () => void;
  onError: (message: string) => void;
}

export async function streamChat(
  body: { conversationId?: string | null; message: string },
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  // The stream must always end in exactly one terminal callback (onDone | onError) —
  // the composer's loading state has nothing else to reset it, so a stream that just
  // stops (function timeout, proxy idle-timeout, network drop) would otherwise leave
  // the UI spinning forever. This wrapper collapses every way a stream can end —
  // server-sent done/error lines, transport exceptions, or silent truncation — into
  // that single guarantee.
  let terminated = false;
  const finishDone = () => {
    if (terminated) return;
    terminated = true;
    handlers.onDone();
  };
  const finishError = (message: string) => {
    if (terminated) return;
    terminated = true;
    handlers.onError(message);
  };

  try {
    let response: Response;
    try {
      response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal,
      });
    } catch {
      finishError("Network error contacting the assistant.");
      return;
    }

    if (!response.ok || !response.body) {
      finishError(await parseError(response));
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    const dispatch = (line: string) => {
      const trimmed = line.trim();
      if (!trimmed) return;
      let event: { type: string; [key: string]: unknown };
      try {
        event = JSON.parse(trimmed);
      } catch {
        return;
      }
      if (event.type === "meta") handlers.onMeta(event as unknown as ChatMeta);
      else if (event.type === "delta") handlers.onDelta(event.text as string);
      else if (event.type === "done") finishDone();
      else if (event.type === "error") finishError(event.error as string);
    };

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) dispatch(line);
    }
    // A final line without a trailing newline would otherwise be dropped silently.
    buffer += decoder.decode();
    dispatch(buffer);

    finishError("The connection was interrupted before the assistant finished.");
  } catch (error) {
    finishError(
      error instanceof Error && error.name === "AbortError"
        ? "The request was cancelled."
        : "The connection to the assistant was lost.",
    );
  }
}
