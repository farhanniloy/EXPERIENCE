"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import { ApiError, apiRequest, jsonBody } from "@/lib/api-client";
import { workflowCopy } from "@/lib/workflow-copy";

type Message = {
  id: string;
  sender_id: string;
  is_mine: boolean;
  body: string;
  created_at: string;
  read_at: string | null;
  moderation_status: "visible" | "pending" | "removed";
};

export function ConversationPanel({ conversationId }: { conversationId: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const current = await apiRequest<Message[]>(`conversations/${conversationId}/messages`);
      const markedAt = new Date().toISOString();
      await apiRequest(`conversations/${conversationId}/read`, {
        method: "POST",
        body: jsonBody({}),
      });
      setMessages(current.map((message) => (
        !message.is_mine && message.moderation_status === "visible" && !message.read_at
          ? { ...message, read_at: markedAt }
          : message
      )));
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiError && reason.status === 404
        ? workflowCopy.messagesUnavailable
        : reason instanceof Error ? reason.message : workflowCopy.messagesLoadError);
    }
  }, [conversationId]);

  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    const poll = async () => {
      if (!active) return;
      await load();
      if (active) timer = window.setTimeout(() => { void poll(); }, 10000);
    };
    timer = window.setTimeout(() => { void poll(); }, 0);
    return () => {
      active = false;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [load]);

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    setError("");
    try {
      await apiRequest<Message>(`conversations/${conversationId}/messages`, {
        method: "POST",
        body: jsonBody({ body: body.trim() }),
      });
      setBody("");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : workflowCopy.messagesLoadError);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-9 border-t border-[#E8E4DC] pt-6">
      <h2 className="text-lg font-semibold">{workflowCopy.messagesTitle}</h2>
      {error ? <p role="alert" className="mt-3 text-sm text-red-700">{error}</p> : null}
      {!messages.length && !error ? <p className="mt-3 text-sm text-[#77736D]">{workflowCopy.messagesNoHistory}</p> : null}
      <ol className="mt-4 max-h-96 space-y-3 overflow-y-auto" aria-live="polite">
        {messages.map((message) => (
          <li key={message.id} className={`max-w-[90%] rounded-2xl p-4 text-sm ${message.is_mine ? "ml-auto bg-[#F7F5F0]" : "bg-white border border-[#E8E4DC]"}`}>
            {message.moderation_status === "removed" ? (
              <p className="text-[#77736D]">{workflowCopy.messageRemoved}</p>
            ) : message.moderation_status === "pending" ? (
              <p className="text-[#77736D]">{workflowCopy.messagePendingModeration}</p>
            ) : (
              <p className="whitespace-pre-wrap break-words">{message.body}</p>
            )}
            <div className="mt-2 flex justify-between gap-4 text-[11px] text-[#77736D]">
              <time dateTime={message.created_at}>{new Intl.DateTimeFormat("en", {
                dateStyle: "short",
                timeStyle: "short",
              }).format(new Date(message.created_at))}</time>
              {message.is_mine && message.read_at ? <span>{workflowCopy.messageRead}</span> : null}
            </div>
          </li>
        ))}
      </ol>
      <form onSubmit={(event) => void send(event)} className="mt-5 flex flex-col gap-3 sm:flex-row">
        <label className="sr-only" htmlFor={`message-${conversationId}`}>{workflowCopy.messageLabel}</label>
        <textarea
          id={`message-${conversationId}`}
          value={body}
          onChange={(event) => setBody(event.target.value)}
          maxLength={5000}
          rows={2}
          placeholder={workflowCopy.messageLabel}
          className="min-h-12 flex-1 resize-y rounded-xl border border-[#E8E4DC] px-4 py-3 text-sm"
        />
        <button type="submit" disabled={busy || !body.trim()} className="h-12 shrink-0 rounded-full bg-[#75404A] px-5 text-sm font-medium text-white disabled:opacity-50">
          {busy ? workflowCopy.messageSending : workflowCopy.messageSend}
        </button>
      </form>
    </section>
  );
}
