"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Nav } from "@/components/layout/nav";
import { ApiError, apiRequest } from "@/lib/api-client";
import { workflowCopy } from "@/lib/workflow-copy";

type Conversation = {
  id: string;
  booking_id: string;
  experience_title: string;
  other_party: string;
  unread_count: number;
  latest_message: string;
  updated_at: string;
};

export function ConversationInbox() {
  const [conversations, setConversations] = useState<Conversation[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      apiRequest<Conversation[]>("conversations")
        .then(setConversations)
        .catch((reason: unknown) => setError(
          reason instanceof ApiError && [401, 403].includes(reason.status)
            ? workflowCopy.messagesSignIn
            : reason instanceof Error ? reason.message : workflowCopy.messagesLoadError,
        ));
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <>
      <Nav />
      <main className="min-h-screen bg-[#F7F5F0] px-4 py-12 text-[#20201F] sm:px-6">
        <section className="mx-auto max-w-3xl">
          <h1 className="text-3xl font-semibold">{workflowCopy.messagesInboxTitle}</h1>
          <p className="mt-2 text-sm text-[#77736D]">{workflowCopy.messagesInboxIntro}</p>
          {error ? <p role="alert" className="mt-6 rounded-xl bg-white p-4 text-sm text-red-700">{error}</p> : null}
          {!conversations && !error ? <p className="mt-6 text-sm text-[#77736D]" aria-live="polite">{workflowCopy.messagesLoading}</p> : null}
          {conversations?.length === 0 ? <p className="mt-6 rounded-2xl border border-[#E8E4DC] bg-white p-6 text-sm text-[#77736D]">{workflowCopy.messagesEmpty}</p> : null}
          {conversations?.length ? (
            <ul className="mt-6 space-y-3">
              {conversations.map((conversation) => (
                <li key={conversation.id}>
                  <Link href={`/bookings/${conversation.booking_id}`} className="block rounded-2xl border border-[#E8E4DC] bg-white p-5 transition hover:border-[#75404A]">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h2 className="font-semibold">{conversation.experience_title}</h2>
                        <p className="mt-1 text-sm text-[#77736D]">{workflowCopy.bookingWith} {conversation.other_party}</p>
                      </div>
                      <span className="text-xs font-medium text-[#75404A]">
                        {conversation.unread_count
                          ? workflowCopy.unreadCount(conversation.unread_count)
                          : workflowCopy.allMessagesRead}
                      </span>
                    </div>
                    {conversation.latest_message ? <p className="mt-4 line-clamp-2 text-sm text-[#77736D]">{conversation.latest_message}</p> : null}
                  </Link>
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      </main>
    </>
  );
}
