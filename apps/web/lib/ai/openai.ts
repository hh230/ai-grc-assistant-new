/**
 * OpenAI adapters for the embedding/chat ports (ADL-0009). Plain `fetch` against the REST
 * API — no SDK dependency. Reads `OPENAI_API_KEY`, `OPENAI_MODEL` (chat), and
 * `OPENAI_EMBEDDING_MODEL` from the environment. Node-only.
 */

import {
  AiProviderError,
  type ChatMessage,
  type ChatProvider,
  type EmbeddingProvider,
} from "./provider";

const OPENAI_BASE_URL = process.env.OPENAI_BASE_URL ?? "https://api.openai.com/v1";

const EMBEDDING_DIMENSIONS: Record<string, number> = {
  "text-embedding-3-large": 3072,
  "text-embedding-3-small": 1536,
  "text-embedding-ada-002": 1536,
};

function apiKey(): string {
  const key = process.env.OPENAI_API_KEY;
  if (!key) throw new AiProviderError("OPENAI_API_KEY is not configured.");
  return key;
}

export class OpenAiEmbeddingProvider implements EmbeddingProvider {
  readonly model = process.env.OPENAI_EMBEDDING_MODEL ?? "text-embedding-3-small";
  readonly id = `openai:${this.model}`;
  readonly dimension = EMBEDDING_DIMENSIONS[this.model] ?? 1536;

  async embed(texts: string[]): Promise<number[][]> {
    if (texts.length === 0) return [];
    const response = await fetch(`${OPENAI_BASE_URL}/embeddings`, {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey()}`, "Content-Type": "application/json" },
      body: JSON.stringify({ model: this.model, input: texts }),
    });
    if (!response.ok) {
      throw new AiProviderError(
        `OpenAI embeddings failed (${response.status}): ${await safeText(response)}`,
      );
    }
    const data = (await response.json()) as { data: { embedding: number[] }[] };
    return data.data.map((item) => item.embedding);
  }
}

export class OpenAiChatProvider implements ChatProvider {
  readonly model = process.env.OPENAI_MODEL ?? "gpt-4o-mini";
  readonly id = `openai:${this.model}`;

  async complete(
    messages: ChatMessage[],
    options: { json?: boolean; maxTokens?: number } = {},
  ): Promise<string> {
    const response = await fetch(`${OPENAI_BASE_URL}/chat/completions`, {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey()}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: this.model,
        messages,
        max_completion_tokens: options.maxTokens ?? 8000,
        ...(options.json ? { response_format: { type: "json_object" } } : {}),
      }),
    });
    if (!response.ok) {
      throw new AiProviderError(
        `OpenAI chat failed (${response.status}): ${await safeText(response)}`,
      );
    }
    const data = (await response.json()) as { choices: { message: { content: string } }[] };
    return data.choices[0]?.message.content ?? "";
  }

  async stream(
    messages: ChatMessage[],
    onDelta: (text: string) => void,
    options: { maxTokens?: number } = {},
  ): Promise<void> {
    const response = await fetch(`${OPENAI_BASE_URL}/chat/completions`, {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey()}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: this.model,
        messages,
        max_completion_tokens: options.maxTokens ?? 8000,
        stream: true,
      }),
    });
    if (!response.ok || !response.body) {
      throw new AiProviderError(
        `OpenAI stream failed (${response.status}): ${await safeText(response)}`,
      );
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
        if (!trimmed.startsWith("data:")) continue;
        const payload = trimmed.slice(5).trim();
        if (payload === "[DONE]") return;
        try {
          const json = JSON.parse(payload) as { choices: { delta?: { content?: string } }[] };
          const delta = json.choices[0]?.delta?.content;
          if (delta) onDelta(delta);
        } catch {
          // Ignore keep-alive / partial frames.
        }
      }
    }
  }
}

async function safeText(response: Response): Promise<string> {
  try {
    return (await response.text()).slice(0, 300);
  } catch {
    return "<no body>";
  }
}
