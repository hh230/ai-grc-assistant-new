-- RAG chat conversations, scoped to BOTH tenant and user — a user only ever sees their own
-- conversations. Messages are append-only, ordered by `seq` (insertion order).
CREATE TABLE IF NOT EXISTS conversations (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  user_id text NOT NULL,
  title text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS conversations_tenant_user_idx ON conversations (tenant_id, user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
  id text PRIMARY KEY,
  conversation_id text NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
  seq bigserial NOT NULL,
  role text NOT NULL,
  content text NOT NULL,
  citations jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chat_messages_conversation_seq_idx ON chat_messages (conversation_id, seq);
