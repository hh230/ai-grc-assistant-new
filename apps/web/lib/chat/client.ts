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
  let response: Response;
  try {
    response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch {
    handlers.onError("Network error contacting the assistant.");
    return;
  }

  if (!response.ok || !response.body) {
    handlers.onError(await parseError(response));
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      let event: { type: string; [key: string]: unknown };
      try {
        event = JSON.parse(trimmed);
      } catch {
        continue;
      }
      if (event.type === "meta") handlers.onMeta(event as unknown as ChatMeta);
      else if (event.type === "delta") handlers.onDelta(event.text as string);
      else if (event.type === "done") handlers.onDone();
      else if (event.type === "error") handlers.onError(event.error as string);
    }
  }
}
