/**
 * AI provider ports. All embedding and chat access goes through these interfaces so the
 * concrete provider (OpenAI now — ADL-0009) is swappable per deployment without touching
 * the pipeline. A deterministic local provider backs the same ports for resilience and
 * offline/dev use. Node-only.
 */

export interface EmbeddingProvider {
  /** Stable identifier recorded with stored vectors (e.g. "openai:text-embedding-3-large"). */
  readonly id: string;
  readonly dimension: number;
  embed(texts: string[]): Promise<number[][]>;
}

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface ChatProvider {
  readonly id: string;
  /** Returns the assistant message content. `json` requests a JSON-object response. */
  complete(
    messages: ChatMessage[],
    options?: { json?: boolean; maxTokens?: number },
  ): Promise<string>;
  /** Streams content deltas; resolves when complete. Used by the P5 chat. */
  stream?(
    messages: ChatMessage[],
    onDelta: (text: string) => void,
    options?: { maxTokens?: number },
  ): Promise<void>;
}

export class AiProviderError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AiProviderError";
  }
}

/** Cosine similarity for ranking stored chunk vectors against a query vector. */
export function cosineSimilarity(a: number[], b: number[]): number {
  let dot = 0;
  let normA = 0;
  let normB = 0;
  const len = Math.min(a.length, b.length);
  for (let i = 0; i < len; i += 1) {
    dot += a[i]! * b[i]!;
    normA += a[i]! * a[i]!;
    normB += b[i]! * b[i]!;
  }
  if (normA === 0 || normB === 0) return 0;
  return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}
