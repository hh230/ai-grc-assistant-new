/**
 * Conversation repository behind a port, backed by PostgreSQL (`conversations` +
 * `chat_messages` tables). Scoped to BOTH tenant and user — a user only ever sees their own
 * conversations. Node-only.
 */

import { getPool } from "@/lib/db/pool";
import type { ChatMessageRecord, ChatRole, Citation, Conversation } from "./types";

export interface ConversationRepository {
  list(tenantId: string, userId: string): Promise<Conversation[]>;
  get(tenantId: string, userId: string, id: string): Promise<Conversation | null>;
  create(conversation: Conversation): Promise<Conversation>;
  appendMessage(
    tenantId: string,
    userId: string,
    id: string,
    message: ChatMessageRecord,
  ): Promise<void>;
  setTitle(tenantId: string, userId: string, id: string, title: string): Promise<void>;
  delete(tenantId: string, userId: string, id: string): Promise<void>;
}

interface ConversationRow {
  id: string;
  tenant_id: string;
  user_id: string;
  title: string;
  created_at: Date;
  updated_at: Date;
}

interface MessageRow {
  id: string;
  conversation_id: string;
  role: ChatRole;
  content: string;
  citations: Citation[] | null;
  created_at: Date;
}

function toMessage(row: MessageRow): ChatMessageRecord {
  return {
    id: row.id,
    role: row.role,
    content: row.content,
    citations: row.citations ?? undefined,
    createdAt: row.created_at.toISOString(),
  };
}

function toConversation(row: ConversationRow, messages: ChatMessageRecord[]): Conversation {
  return {
    id: row.id,
    tenantId: row.tenant_id,
    userId: row.user_id,
    title: row.title,
    createdAt: row.created_at.toISOString(),
    updatedAt: row.updated_at.toISOString(),
    messages,
  };
}

async function fetchMessages(conversationIds: string[]): Promise<Map<string, ChatMessageRecord[]>> {
  const byConversation = new Map<string, ChatMessageRecord[]>();
  if (conversationIds.length === 0) return byConversation;
  const { rows } = await getPool().query<MessageRow>(
    `SELECT * FROM chat_messages WHERE conversation_id = ANY($1) ORDER BY seq ASC`,
    [conversationIds],
  );
  for (const row of rows) {
    const list = byConversation.get(row.conversation_id) ?? [];
    list.push(toMessage(row));
    byConversation.set(row.conversation_id, list);
  }
  return byConversation;
}

class PostgresConversationRepository implements ConversationRepository {
  async list(tenantId: string, userId: string): Promise<Conversation[]> {
    const { rows } = await getPool().query<ConversationRow>(
      `SELECT * FROM conversations WHERE tenant_id = $1 AND user_id = $2 ORDER BY updated_at DESC`,
      [tenantId, userId],
    );
    const messagesByConversation = await fetchMessages(rows.map((r) => r.id));
    return rows.map((row) => toConversation(row, messagesByConversation.get(row.id) ?? []));
  }

  async get(tenantId: string, userId: string, id: string): Promise<Conversation | null> {
    const { rows } = await getPool().query<ConversationRow>(
      `SELECT * FROM conversations WHERE id = $1 AND tenant_id = $2 AND user_id = $3`,
      [id, tenantId, userId],
    );
    const row = rows[0];
    if (!row) return null;
    const messagesByConversation = await fetchMessages([row.id]);
    return toConversation(row, messagesByConversation.get(row.id) ?? []);
  }

  async create(conversation: Conversation): Promise<Conversation> {
    await getPool().query(
      `INSERT INTO conversations (id, tenant_id, user_id, title, created_at, updated_at)
       VALUES ($1,$2,$3,$4,$5,$6)`,
      [
        conversation.id,
        conversation.tenantId,
        conversation.userId,
        conversation.title,
        conversation.createdAt,
        conversation.updatedAt,
      ],
    );
    return conversation;
  }

  async appendMessage(
    tenantId: string,
    userId: string,
    id: string,
    message: ChatMessageRecord,
  ): Promise<void> {
    const client = await getPool().connect();
    try {
      await client.query("BEGIN");
      const { rowCount } = await client.query(
        `SELECT 1 FROM conversations WHERE id = $1 AND tenant_id = $2 AND user_id = $3 FOR UPDATE`,
        [id, tenantId, userId],
      );
      if (!rowCount) {
        await client.query("ROLLBACK");
        return;
      }
      await client.query(
        `INSERT INTO chat_messages (id, conversation_id, role, content, citations, created_at)
         VALUES ($1,$2,$3,$4,$5,$6)`,
        [
          message.id,
          id,
          message.role,
          message.content,
          message.citations ? JSON.stringify(message.citations) : null,
          message.createdAt,
        ],
      );
      await client.query(`UPDATE conversations SET updated_at = now() WHERE id = $1`, [id]);
      await client.query("COMMIT");
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  }

  async setTitle(tenantId: string, userId: string, id: string, title: string): Promise<void> {
    await getPool().query(
      `UPDATE conversations SET title = $4 WHERE id = $1 AND tenant_id = $2 AND user_id = $3`,
      [id, tenantId, userId, title],
    );
  }

  async delete(tenantId: string, userId: string, id: string): Promise<void> {
    await getPool().query(
      `DELETE FROM conversations WHERE id = $1 AND tenant_id = $2 AND user_id = $3`,
      [id, tenantId, userId],
    );
  }
}

export const conversationRepository: ConversationRepository =
  new PostgresConversationRepository();
