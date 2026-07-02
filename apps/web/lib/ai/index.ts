/**
 * Provider factory. Selects the embedding/chat provider from configuration:
 *   AI_PROVIDER=openai (default when OPENAI_API_KEY is set) → OpenAI (ADL-0009)
 *   AI_PROVIDER=local  (or no key)                          → deterministic local fallback
 * Callers depend only on the ports, never on a concrete provider.
 */

import { LocalChatProvider, LocalEmbeddingProvider } from "./local";
import { OpenAiChatProvider, OpenAiEmbeddingProvider } from "./openai";
import type { ChatProvider, EmbeddingProvider } from "./provider";

function isOpenAiConfigured(): boolean {
  const explicit = process.env.AI_PROVIDER?.toLowerCase();
  if (explicit === "local") return false;
  if (explicit === "openai") return true;
  return Boolean(process.env.OPENAI_API_KEY);
}

export function getEmbeddingProvider(): EmbeddingProvider {
  return isOpenAiConfigured() ? new OpenAiEmbeddingProvider() : new LocalEmbeddingProvider();
}

export function getChatProvider(): ChatProvider {
  return isOpenAiConfigured() ? new OpenAiChatProvider() : new LocalChatProvider();
}

export { AiProviderError, cosineSimilarity } from "./provider";
export type { ChatMessage, ChatProvider, EmbeddingProvider } from "./provider";
