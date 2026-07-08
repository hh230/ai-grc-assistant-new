"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import {
  ArrowUp,
  FileText,
  Loader2,
  MessageSquarePlus,
  Sparkles,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { useSession } from "@/components/auth/SessionProvider";
import {
  useConversations,
  useDeleteConversation,
  useRefreshConversations,
} from "@/hooks/useConversations";
import { fetchConversation, streamChat } from "@/lib/chat/client";
import type { ChatMessageRecord, Citation } from "@/lib/chat/types";
import { cn } from "@/lib/utils";

const SUGGESTION_KEYS = ["accessControl", "frameworksCovered", "passwordMfa", "iso27001Gaps"] as const;

export function ChatWorkspace() {
  const { user } = useSession();
  const t = useTranslations("aiAssistant");
  const { data: conversations } = useConversations();
  const refreshConversations = useRefreshConversations();
  const deleteConversation = useDeleteConversation();

  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageRecord[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [streamingCitations, setStreamingCitations] = useState<Citation[]>([]);
  const [error, setError] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streamingText]);

  async function openConversation(id: string) {
    if (streaming) return;
    setActiveId(id);
    setError(null);
    const conversation = await fetchConversation(id);
    setMessages(conversation.messages);
  }

  function newConversation() {
    if (streaming) return;
    setActiveId(null);
    setMessages([]);
    setError(null);
    setInput("");
  }

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || streaming) return;

    const userMessage: ChatMessageRecord = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
      createdAt: new Date().toISOString(),
    };
    setMessages((current) => [...current, userMessage]);
    setInput("");
    setStreaming(true);
    setStreamingText("");
    setStreamingCitations([]);
    setError(null);

    let accumulated = "";
    let citations: Citation[] = [];

    const appendAssistantMessage = () => {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: accumulated || t("noResponse"),
          citations,
          createdAt: new Date().toISOString(),
        },
      ]);
    };

    try {
      await streamChat(
        { conversationId: activeId, message: trimmed },
        {
          onMeta: (meta) => {
            citations = meta.citations;
            setStreamingCitations(meta.citations);
            setActiveId(meta.conversationId);
            refreshConversations();
          },
          onDelta: (delta) => {
            accumulated += delta;
            setStreamingText(accumulated);
          },
          onDone: () => {
            appendAssistantMessage();
            refreshConversations();
          },
          onError: (message) => {
            // Keep whatever the assistant managed to say before the failure — a partial
            // grounded answer plus a visible error beats silently discarding it.
            if (accumulated) appendAssistantMessage();
            setError(message);
          },
        },
      );
    } catch {
      setError(t("unexpectedError"));
    } finally {
      // The composer must never stay locked, no matter how the stream ended.
      setStreaming(false);
      setStreamingText("");
      setStreamingCitations([]);
    }
  }

  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send(input);
    }
  }

  const isEmpty = messages.length === 0 && !streaming;

  return (
    <div className="flex h-[calc(100vh-9.5rem)] gap-5">
      {/* Conversation history */}
      <aside className="hidden w-64 shrink-0 flex-col rounded-2xl border border-hairline bg-surface md:flex">
        <div className="p-3">
          <button
            type="button"
            onClick={newConversation}
            className="inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-lg bg-accent text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90 active:scale-[0.98]"
          >
            <MessageSquarePlus className="h-4 w-4" strokeWidth={2} />
            {t("newChat")}
          </button>
        </div>
        <div className="scrollbar-thin flex-1 space-y-0.5 overflow-y-auto px-2 pb-2">
          {(conversations ?? []).map((conversation) => (
            <div
              key={conversation.id}
              className={cn(
                "group flex items-center gap-1 rounded-lg px-2 py-2 text-sm transition-colors duration-150",
                conversation.id === activeId ? "bg-white/[0.05]" : "hover:bg-white/[0.03]",
              )}
            >
              <button
                type="button"
                onClick={() => void openConversation(conversation.id)}
                className="min-w-0 flex-1 truncate text-start text-foreground-secondary group-hover:text-foreground"
              >
                {conversation.title}
              </button>
              <button
                type="button"
                onClick={() => {
                  deleteConversation.mutate(conversation.id);
                  if (conversation.id === activeId) newConversation();
                }}
                className="shrink-0 rounded p-1 text-foreground-muted opacity-0 transition-opacity duration-150 hover:text-danger group-hover:opacity-100"
                aria-label={t("deleteConversation")}
              >
                <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
              </button>
            </div>
          ))}
          {(conversations ?? []).length === 0 && (
            <p className="px-2 py-4 text-center text-2xs text-foreground-muted">
              {t("noConversations")}
            </p>
          )}
        </div>
      </aside>

      {/* Thread */}
      <div className="flex min-w-0 flex-1 flex-col rounded-2xl border border-hairline bg-surface">
        <div ref={scrollRef} className="scrollbar-thin flex-1 overflow-y-auto px-4 py-6 sm:px-6">
          {isEmpty ? (
            <EmptyState onPick={(s) => void send(s)} />
          ) : (
            <div className="mx-auto max-w-2xl space-y-5">
              {messages.map((message) => (
                <ChatBubble key={message.id} message={message} initials={user.initials} />
              ))}
              {streaming && (
                <ChatBubble
                  message={{
                    id: "streaming",
                    role: "assistant",
                    content: streamingText,
                    citations: streamingCitations,
                    createdAt: "",
                  }}
                  initials={user.initials}
                  pending
                />
              )}
              {error && (
                <div className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-soft px-3 py-2.5 text-sm text-foreground">
                  <TriangleAlert
                    className="mt-0.5 h-4 w-4 shrink-0 text-danger"
                    strokeWidth={1.75}
                  />
                  <span>{error}</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Composer */}
        <div className="border-t border-hairline p-3 sm:p-4">
          <div className="mx-auto flex max-w-2xl items-end gap-2 rounded-xl border border-hairline bg-surface/60 px-3 py-2 focus-within:border-hairline-strong">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onComposerKeyDown}
              rows={1}
              placeholder={t("composerPlaceholder")}
              className="scrollbar-thin max-h-32 min-h-[24px] flex-1 resize-none bg-transparent text-sm text-foreground outline-none placeholder:text-foreground-muted"
            />
            <button
              type="button"
              onClick={() => void send(input)}
              disabled={streaming || !input.trim()}
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-white transition-opacity duration-150 hover:opacity-90 disabled:opacity-40"
              aria-label={t("sendMessage")}
            >
              {streaming ? (
                <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
              ) : (
                <ArrowUp className="h-4 w-4" strokeWidth={2} />
              )}
            </button>
          </div>
          <p className="mx-auto mt-2 max-w-2xl text-center text-2xs text-foreground-muted">
            {t("groundedFooter")}
          </p>
        </div>
      </div>
    </div>
  );
}

function ChatBubble({
  message,
  initials,
  pending,
}: {
  message: ChatMessageRecord;
  initials: string;
  pending?: boolean;
}) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <span
        className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-2xs font-semibold",
          isUser
            ? "bg-gradient-to-br from-accent/40 to-accent/10 text-accent-foreground"
            : "border border-hairline bg-surface-2 text-accent-foreground",
        )}
      >
        {isUser ? initials : <Sparkles className="h-3.5 w-3.5" strokeWidth={1.75} />}
      </span>
      <div className={cn("min-w-0 max-w-[85%]", isUser && "flex flex-col items-end")}>
        <div
          className={cn(
            "rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed",
            isUser
              ? "bg-accent text-white"
              : "border border-hairline bg-surface/40 text-foreground-secondary",
          )}
        >
          <p className="whitespace-pre-wrap break-words">
            {message.content}
            {pending && (
              <span className="ms-0.5 inline-block h-3.5 w-1.5 animate-pulse bg-accent-foreground align-middle" />
            )}
          </p>
        </div>
        {!isUser && message.citations && message.citations.length > 0 && (
          <Citations citations={message.citations} />
        )}
      </div>
    </div>
  );
}

function Citations({ citations }: { citations: Citation[] }) {
  const t = useTranslations("aiAssistant");
  return (
    <div className="mt-2">
      <p className="mb-1 text-2xs font-medium uppercase tracking-wider text-foreground-muted">
        {t("sources")}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {citations.map((citation) => (
          <Link
            key={`${citation.documentId}-${citation.chunkIndex}`}
            href={`/analysis?doc=${citation.documentId}`}
            title={citation.snippet}
            className="inline-flex items-center gap-1.5 rounded-full border border-hairline bg-surface/60 px-2 py-0.5 text-2xs text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:text-foreground"
          >
            <span className="font-mono text-accent-foreground">[{citation.index}]</span>
            <FileText className="h-3 w-3" strokeWidth={1.75} />
            <span className="max-w-[180px] truncate">{citation.fileName}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (suggestion: string) => void }) {
  const t = useTranslations("aiAssistant");
  return (
    <div className="mx-auto flex max-w-md flex-col items-center pt-10 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2 shadow-soft">
        <Sparkles className="h-5 w-5 text-accent-foreground" strokeWidth={1.75} />
      </div>
      <h2 className="mt-4 text-base font-semibold tracking-tight text-foreground">
        {t("emptyTitle")}
      </h2>
      <p className="mt-1 text-sm text-foreground-secondary">{t("emptyDescription")}</p>
      <div className="mt-6 grid w-full gap-2">
        {SUGGESTION_KEYS.map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => onPick(t(`suggestions.${key}`))}
            className="rounded-lg border border-hairline bg-surface/60 px-3 py-2 text-start text-sm text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:text-foreground"
          >
            {t(`suggestions.${key}`)}
          </button>
        ))}
      </div>
    </div>
  );
}
