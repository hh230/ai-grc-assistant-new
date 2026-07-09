/**
 * OpenAI adapters for the embedding/chat ports (ADL-0009). Plain `fetch` against the REST
 * API — no SDK dependency. Reads `OPENAI_API_KEY`, `OPENAI_MODEL` (chat), and
 * `OPENAI_EMBEDDING_MODEL` from the environment. Node-only.
 *
 * Every request is bounded by an `AbortController` timeout and retried once on a transient
 * failure (network error, timeout, or 5xx) — without this, a hung upstream response blocks
 * the calling serverless function until the platform kills it, which (for the background
 * analysis pipeline) silently abandons the run with no rejection for `runPipeline`'s caller
 * to catch, leaving the record stuck on "processing" forever (see `analysis/service.ts`'s
 * `reconcileStaleAnalyses`, the backstop for the case this still doesn't prevent).
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

// Non-streaming calls: bounded by a hard timeout, retried once on a transient failure.
const EMBED_TIMEOUT_MS = Number(process.env.OPENAI_EMBED_TIMEOUT_MS ?? 60_000);
// A non-streaming structured assessment (assess() in analysis/service.ts, up to 20k
// max_completion_tokens on a reasoning model) can legitimately run well past 90s — observed
// in practice via arabicAnalysis.eval.ts timing out at exactly the old 90s bound on a normal,
// eventually-successful call. 180s leaves headroom for genuine reasoning time without
// papering over a real hang (still far short of the analyze route's 300s maxDuration).
const CHAT_TIMEOUT_MS = Number(process.env.OPENAI_CHAT_TIMEOUT_MS ?? 180_000);
// Streaming calls run far longer in total (a reasoning model can legitimately take minutes),
// so they're bounded by inactivity instead of total duration: aborted only if no chunk (not
// even a keep-alive event) arrives for this long.
const STREAM_STALL_TIMEOUT_MS = Number(process.env.OPENAI_STREAM_STALL_TIMEOUT_MS ?? 60_000);
const MAX_RETRIES = 2;
const RETRY_BASE_DELAY_MS = 500;

function apiKey(): string {
  const key = process.env.OPENAI_API_KEY;
  if (!key) throw new AiProviderError("OPENAI_API_KEY is not configured.");
  return key;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** True for failures worth retrying: our own timeout abort, a network-level failure (no
 * response at all), or an upstream 5xx. Never retries 4xx (bad request/auth/rate-limit
 * shape won't change on retry) or a schema/parse problem, which is the caller's job. */
function isRetryable(error: unknown): boolean {
  if (error instanceof AiProviderError) {
    return /timed out|network error|\(5\d\d\)/.test(error.message);
  }
  return false;
}

async function withRetry<T>(fn: () => Promise<T>, attempts = MAX_RETRIES): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt <= attempts; attempt += 1) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      if (attempt === attempts || !isRetryable(error)) throw error;
      await sleep(RETRY_BASE_DELAY_MS * 2 ** attempt);
    }
  }
  throw lastError;
}

/** `fetch` bounded by an `AbortController` timeout, normalized to a single error type so
 * `isRetryable` can recognize it regardless of whether the failure was a timeout or a
 * lower-level network error (both throw before any `Response` exists). */
async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    if (controller.signal.aborted) {
      throw new AiProviderError(`OpenAI request timed out after ${timeoutMs}ms`);
    }
    throw new AiProviderError(
      `OpenAI request network error: ${error instanceof Error ? error.message : String(error)}`,
    );
  } finally {
    clearTimeout(timer);
  }
}

export class OpenAiEmbeddingProvider implements EmbeddingProvider {
  readonly model = process.env.OPENAI_EMBEDDING_MODEL ?? "text-embedding-3-small";
  readonly id = `openai:${this.model}`;
  readonly dimension = EMBEDDING_DIMENSIONS[this.model] ?? 1536;

  async embed(texts: string[]): Promise<number[][]> {
    if (texts.length === 0) return [];
    return withRetry(async () => {
      const response = await fetchWithTimeout(
        `${OPENAI_BASE_URL}/embeddings`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${apiKey()}`, "Content-Type": "application/json" },
          body: JSON.stringify({ model: this.model, input: texts }),
        },
        EMBED_TIMEOUT_MS,
      );
      if (!response.ok) {
        throw new AiProviderError(
          `OpenAI embeddings failed (${response.status}): ${await safeText(response)}`,
        );
      }
      const data = (await response.json()) as { data: { embedding: number[] }[] };
      return data.data.map((item) => item.embedding);
    });
  }
}

export class OpenAiChatProvider implements ChatProvider {
  readonly model = process.env.OPENAI_MODEL ?? "gpt-4o-mini";
  readonly id = `openai:${this.model}`;

  async complete(
    messages: ChatMessage[],
    options: { json?: boolean; maxTokens?: number } = {},
  ): Promise<string> {
    return withRetry(async () => {
      const response = await fetchWithTimeout(
        `${OPENAI_BASE_URL}/chat/completions`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${apiKey()}`, "Content-Type": "application/json" },
          body: JSON.stringify({
            model: this.model,
            messages,
            max_completion_tokens: options.maxTokens ?? 8000,
            ...(options.json ? { response_format: { type: "json_object" } } : {}),
          }),
        },
        CHAT_TIMEOUT_MS,
      );
      if (!response.ok) {
        throw new AiProviderError(
          `OpenAI chat failed (${response.status}): ${await safeText(response)}`,
        );
      }
      const data = (await response.json()) as { choices: { message: { content: string } }[] };
      return data.choices[0]?.message.content ?? "";
    });
  }

  async stream(
    messages: ChatMessage[],
    onDelta: (text: string) => void,
    options: { maxTokens?: number } = {},
  ): Promise<void> {
    // A stall timeout that resets on every received chunk — not a single overall
    // AbortController timeout, since a real reasoning-model stream can legitimately run for
    // minutes. Only silence (no bytes at all, including keep-alives) for this long aborts it.
    const controller = new AbortController();
    let stallTimer: ReturnType<typeof setTimeout> | undefined;
    const armStallTimer = () => {
      clearTimeout(stallTimer);
      stallTimer = setTimeout(() => controller.abort(), STREAM_STALL_TIMEOUT_MS);
    };
    armStallTimer();

    let response: Response;
    try {
      response = await fetch(`${OPENAI_BASE_URL}/chat/completions`, {
        method: "POST",
        headers: { Authorization: `Bearer ${apiKey()}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          model: this.model,
          messages,
          max_completion_tokens: options.maxTokens ?? 8000,
          stream: true,
        }),
        signal: controller.signal,
      });
    } catch (error) {
      clearTimeout(stallTimer);
      if (controller.signal.aborted) {
        throw new AiProviderError(`OpenAI stream stalled (no response) for ${STREAM_STALL_TIMEOUT_MS}ms`);
      }
      throw new AiProviderError(
        `OpenAI stream network error: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
    if (!response.ok || !response.body) {
      clearTimeout(stallTimer);
      throw new AiProviderError(
        `OpenAI stream failed (${response.status}): ${await safeText(response)}`,
      );
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    try {
      for (;;) {
        let chunk: ReadableStreamReadResult<Uint8Array>;
        try {
          chunk = await reader.read();
        } catch (error) {
          if (controller.signal.aborted) {
            throw new AiProviderError(
              `OpenAI stream stalled (no data) for ${STREAM_STALL_TIMEOUT_MS}ms`,
            );
          }
          throw error;
        }
        const { done, value } = chunk;
        if (done) break;
        armStallTimer();
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
    } finally {
      clearTimeout(stallTimer);
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
