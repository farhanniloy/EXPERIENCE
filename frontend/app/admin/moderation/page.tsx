"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Nav } from "@/components/layout/nav";
import { ApiError, apiRequest, jsonBody } from "@/lib/api-client";
import { workflowCopy } from "@/lib/workflow-copy";

type QueueItem = {
  id: string;
  queue_type: string;
  flagged_fields: Record<string, string[]>;
  content: Record<string, string>;
  host: string;
  host_slug: string;
  host_status: string;
  experience: { id: string; title: string; status: string } | null;
  created_at: string;
};

export default function ModerationPage() {
  const [items, setItems] = useState<QueueItem[] | null>(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");

  const load = useCallback(() => {
    apiRequest<QueueItem[]>("admin/moderation")
      .then(setItems)
      .catch((reason: unknown) => setError(
        reason instanceof ApiError && reason.status === 403
          ? "This moderation queue is available to staff moderators only."
          : reason instanceof Error ? reason.message : "Could not load the moderation queue.",
      ));
  }, []);

  useEffect(() => load(), [load]);

  async function review(item: QueueItem, action: "approve" | "reject") {
    setBusyId(item.id);
    setError("");
    try {
      await apiRequest(`admin/moderation/${item.id}`, {
        method: "POST",
        body: jsonBody({ action }),
      });
      setItems((current) => current?.filter((entry) => entry.id !== item.id) ?? []);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not review this item.");
    } finally {
      setBusyId("");
    }
  }

  return (
    <>
      <Nav />
      <main className="min-h-screen bg-[#F7F5F0] px-4 py-12 text-[#20201F] sm:px-6">
        <div className="mx-auto max-w-5xl">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">Staff workspace</p>
          <h1 className="mt-3 text-3xl font-semibold">{workflowCopy.moderationTitle}</h1>
          <p className="mt-2 text-sm text-[#77736D]">Review host applications, first listings, and automatically flagged content.</p>
          {error ? <p role="alert" className="mt-6 rounded-xl bg-white p-4 text-sm text-red-700">{error}</p> : null}
          {items === null && !error ? <p className="mt-8 text-sm text-[#77736D]">Loading moderation items…</p> : null}
          {items?.length === 0 ? <p className="mt-8 rounded-2xl border border-[#E8E4DC] bg-white p-6 text-sm text-[#77736D]">{workflowCopy.noModerationItems}</p> : null}
          <div className="mt-6 space-y-4">
            {items?.map((item) => (
              <article key={item.id} className="rounded-2xl border border-[#E8E4DC] bg-white p-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#75404A]">{item.queue_type.replaceAll("_", " ")}</p>
                    <h2 className="mt-2 text-lg font-semibold">
                      {item.experience?.title ?? item.host}
                    </h2>
                    <p className="mt-1 text-sm text-[#77736D]">
                      Host: {item.host} · Profile: {item.host_status.replaceAll("_", " ")}
                    </p>
                    <Link href={`/companions/${item.host_slug}`} className="mt-2 inline-flex text-sm font-medium text-[#75404A]">
                      View public host profile
                    </Link>
                  </div>
                  <time className="text-xs text-[#77736D]" dateTime={item.created_at}>
                    {new Date(item.created_at).toLocaleString()}
                  </time>
                </div>
                {Object.keys(item.flagged_fields).length > 0 ? (
                  <div className="mt-5 rounded-xl bg-[#F7F5F0] p-4">
                    <p className="text-sm font-medium">Automatic content flags</p>
                    <ul className="mt-2 space-y-1 text-sm text-[#77736D]">
                      {Object.entries(item.flagged_fields).map(([field, reasons]) => (
                        <li key={field} className="border-t border-[#E8E4DC] py-2">
                          <span className="font-medium text-[#20201F]">{field} · {reasons.join(", ")}</span>
                          <p className="mt-1 whitespace-pre-wrap break-words">{item.content[field]}</p>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <p className="mt-4 text-sm text-[#77736D]">No automatic flags. Moderator approval is required before publication.</p>
                )}
                {item.experience && item.host_status !== "approved" ? (
                  <p className="mt-4 text-sm text-[#75404A]">Approve the host application before reviewing this experience for publication.</p>
                ) : null}
                <div className="mt-5 flex flex-wrap gap-3">
                  <button type="button" disabled={busyId === item.id || Boolean(item.experience && item.host_status !== "approved")} onClick={() => void review(item, "approve")} className="h-11 rounded-full bg-[#75404A] px-5 text-sm font-medium text-white disabled:opacity-60">
                    {busyId === item.id ? "Saving…" : "Approve"}
                  </button>
                  <button type="button" disabled={busyId === item.id} onClick={() => void review(item, "reject")} className="h-11 rounded-full border border-[#E8E4DC] px-5 text-sm font-medium text-[#20201F] disabled:opacity-60">
                    Reject
                  </button>
                </div>
              </article>
            ))}
          </div>
        </div>
      </main>
    </>
  );
}
