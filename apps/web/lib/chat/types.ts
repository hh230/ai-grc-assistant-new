/**
 * Chat domain types. A conversation is an ordered list of messages between a user and the
 * grounded AI assistant; assistant messages carry the citations that back their claims.
 */

export interface Citation {
  /** 1-based marker the assistant references in text, e.g. [1]. */
  index: number;
  documentId: string;
  fileName: string;
  chunkIndex: number;
  snippet: string;
  score: number;
}

export type ChatRole = "user" | "assistant";

export interface ChatMessageRecord {
  id: string;
  role: ChatRole;
  content: string;
  citations?: Citation[];
  createdAt: string;
}

export interface Conversation {
  id: string;
  tenantId: string;
  userId: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: ChatMessageRecord[];
}

export interface ConversationSummary {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}

export function toConversationSummary(conversation: Conversation): ConversationSummary {
  return {
    id: conversation.id,
    title: conversation.title,
    createdAt: conversation.createdAt,
    updatedAt: conversation.updatedAt,
    messageCount: conversation.messages.length,
  };
}
