/**
 * Chat/RAG service. Retrieves grounding from the tenant's indexed documents (the P4 vector
 * store), assembles numbered citations, and builds the prompt the streaming route generates
 * from. Enforces read permission on `knowledge_source` and keeps everything tenant-scoped.
 * Node-only.
 */

import { randomUUID } from "node:crypto";
import { ForbiddenError, NotFoundError } from "@/lib/errors";
import { can } from "@/lib/auth/permissions";
import type { ActorContext } from "@/lib/auth/actor";
import { getEmbeddingProvider, type ChatMessage } from "@/lib/ai";
import { vectorStore } from "@/lib/analysis/vector-store";
import { getRequestLocale } from "@/lib/i18n/request-locale";
import type { AppLocale } from "@/i18n/routing";
import { conversationRepository } from "./repository";
import type { ChatMessageRecord, Citation, Conversation } from "./types";

const TOP_K = 6;
const SNIPPET_CHARS = 700;
const HISTORY_WINDOW = 8;

function ensureCanChat(actor: ActorContext): void {
  if (!can(actor.roles, "read", "knowledge_source")) {
    throw new ForbiddenError("You are not permitted to use the AI assistant.");
  }
}

export async function listConversations(actor: ActorContext): Promise<Conversation[]> {
  ensureCanChat(actor);
  return conversationRepository.list(actor.tenantId, actor.userId);
}

export async function getConversation(actor: ActorContext, id: string): Promise<Conversation> {
  ensureCanChat(actor);
  const conversation = await conversationRepository.get(actor.tenantId, actor.userId, id);
  if (!conversation) throw new NotFoundError("Conversation not found.");
  return conversation;
}

export async function deleteConversation(actor: ActorContext, id: string): Promise<void> {
  ensureCanChat(actor);
  await conversationRepository.delete(actor.tenantId, actor.userId, id);
}

export interface PreparedTurn {
  conversation: Conversation;
  citations: Citation[];
  llmMessages: ChatMessage[];
}

/** Load/create the conversation, append the user turn, and retrieve grounding. */
export async function prepareTurn(
  actor: ActorContext,
  conversationId: string | null,
  userText: string,
): Promise<PreparedTurn> {
  ensureCanChat(actor);
  const now = new Date().toISOString();

  let conversation: Conversation;
  if (conversationId) {
    const existing = await conversationRepository.get(actor.tenantId, actor.userId, conversationId);
    if (!existing) throw new NotFoundError("Conversation not found.");
    conversation = existing;
  } else {
    conversation = {
      id: randomUUID(),
      tenantId: actor.tenantId,
      userId: actor.userId,
      title: deriveTitle(userText),
      createdAt: now,
      updatedAt: now,
      messages: [],
    };
    await conversationRepository.create(conversation);
  }

  const userMessage: ChatMessageRecord = {
    id: randomUUID(),
    role: "user",
    content: userText,
    createdAt: now,
  };
  await conversationRepository.appendMessage(
    actor.tenantId,
    actor.userId,
    conversation.id,
    userMessage,
  );

  const citations = await retrieve(actor, userText);
  const locale = await getRequestLocale();
  const llmMessages = buildMessages(conversation.messages, citations, userText, locale);

  return {
    conversation: { ...conversation, messages: [...conversation.messages, userMessage] },
    citations,
    llmMessages,
  };
}

export async function finalizeTurn(
  actor: ActorContext,
  conversationId: string,
  assistantText: string,
  citations: Citation[],
): Promise<ChatMessageRecord> {
  const message: ChatMessageRecord = {
    id: randomUUID(),
    role: "assistant",
    content: assistantText,
    citations,
    createdAt: new Date().toISOString(),
  };
  await conversationRepository.appendMessage(actor.tenantId, actor.userId, conversationId, message);
  return message;
}

async function retrieve(actor: ActorContext, query: string): Promise<Citation[]> {
  const [queryVector] = await getEmbeddingProvider().embed([query]);
  if (!queryVector) return [];
  const hits = await vectorStore.search(actor.tenantId, queryVector, TOP_K);
  return hits
    .filter((hit) => hit.score > 0.05)
    .map((hit, i) => ({
      index: i + 1,
      documentId: hit.documentId,
      fileName: hit.fileName,
      chunkIndex: hit.chunk.index,
      snippet: hit.chunk.text.slice(0, SNIPPET_CHARS),
      score: Number(hit.score.toFixed(4)),
    }));
}

function buildMessages(
  history: ChatMessageRecord[],
  citations: Citation[],
  userText: string,
  locale: AppLocale,
): ChatMessage[] {
  const context =
    citations.length > 0
      ? citations.map((c) => `[${c.index}] (${c.fileName}): ${c.snippet}`).join("\n\n")
      : "No relevant excerpts were found in the knowledge base.";

  const messages: ChatMessage[] = [
    {
      role: "system",
      content:
        "You are the Sentinel GRC assistant — a senior Governance, Risk & Compliance advisor, " +
        "not a general-purpose chatbot. Answer the user's question using ONLY the numbered context " +
        "excerpts provided; cite every grounded claim inline with its source marker, e.g. [1] or " +
        "[2]. If the context does not contain the answer, say plainly that you don't have enough " +
        "information in the indexed knowledge base and suggest what to upload — never fabricate " +
        "facts, control IDs, statistics, or citations, and never speculate on compliance matters. " +
        "Structure substantive answers for an executive reader: lead with a direct, one-sentence " +
        "answer, then supporting detail as short paragraphs or bullet points, citing sources inline. " +
        "For a simple greeting or clarifying question, respond briefly and conversationally instead " +
        "— do not force structure where it doesn't fit. Avoid generic AI filler phrasing (e.g. " +
        '"it is important to note", "as an AI"). ' +
        languageInstruction(locale),
    },
    { role: "system", content: `Context excerpts:\n\n${context}` },
  ];

  for (const message of history.slice(-HISTORY_WINDOW)) {
    messages.push({ role: message.role, content: message.content });
  }
  messages.push({ role: "user", content: userText });
  return messages;
}

function languageInstruction(locale: AppLocale): string {
  if (locale === "ar") {
    return (
      "Respond entirely in professional, formal Modern Standard Arabic (فصحى), in the tone of " +
      "a senior GRC advisor — except for internationally recognized framework names/codes " +
      "(e.g. ISO 27001, NIST CSF, PDPL, NCA ECC, SAMA, COBIT, COSO, CIS), which stay in English " +
      "exactly as written."
    );
  }
  return "Respond in professional, formal business English.";
}

function deriveTitle(text: string): string {
  const clean = text.trim().replace(/\s+/g, " ");
  return clean.length > 60 ? `${clean.slice(0, 57)}…` : clean || "New conversation";
}
