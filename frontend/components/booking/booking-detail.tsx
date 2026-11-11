"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { Nav } from "@/components/layout/nav";
import { ApiError, apiRequest, jsonBody } from "@/lib/api-client";
import { ConversationPanel } from "@/components/booking/conversation-panel";
import { formatPrice } from "@/lib/currency";
import { workflowCopy } from "@/lib/workflow-copy";

type Booking = {
  id: string;
  conversation_id: string | null;
  other_party_user_id: string | null;
  status: string;
  start_at: string;
  end_at: string;
  timezone: string;
  experience_title: string;
  other_party: string;
  viewer_role: "customer" | "host";
  public_venue_name: string;
  customer_note: string;
  total_minor: number;
  currency: string;
  payment_deadline: string | null;
};
type BookingEvent = {
  event_type: string;
  previous_state: string;
  new_state: string;
  created_at: string;
};
type Action = "accept" | "decline" | "cancel" | "start" | "complete";
type Payment = { id: string; provider: string; checkout_url: string | null };

export function BookingDetail({ bookingId }: { bookingId: string }) {
  const router = useRouter();
  const [booking, setBooking] = useState<Booking | null>(null);
  const [events, setEvents] = useState<BookingEvent[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [paymentBusy, setPaymentBusy] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [blockBusy, setBlockBusy] = useState(false);
  const [safetyMessage, setSafetyMessage] = useState("");
  const [reportOpen, setReportOpen] = useState(false);
  const [reportBusy, setReportBusy] = useState(false);
  const [reviewMessage, setReviewMessage] = useState("");
  const paymentKey = useRef<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [bookingData, eventData] = await Promise.all([
        apiRequest<Booking>(`bookings/${bookingId}`),
        apiRequest<BookingEvent[]>(`bookings/${bookingId}/events`),
      ]);
      setBooking(bookingData);
      setEvents(eventData);
      setError("");
    } catch (reason) {
      setError(
        reason instanceof ApiError && reason.status === 404
          ? workflowCopy.bookingNotFound
          : reason instanceof Error ? reason.message : workflowCopy.bookingLoadError,
      );
    }
  }, [bookingId]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function act(action: Action) {
    setBusy(true);
    setError("");
    try {
      const updated = await apiRequest<Booking>(`bookings/${bookingId}/${action}`, {
        method: "POST",
        body: jsonBody({}),
      });
      setBooking(updated);
      const updatedEvents = await apiRequest<BookingEvent[]>(`bookings/${bookingId}/events`);
      setEvents(updatedEvents);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : workflowCopy.bookingActionError);
    } finally {
      setBusy(false);
    }
  }

  async function pay() {
    if (!booking) return;
    setPaymentBusy(true);
    setError("");
    paymentKey.current ??= crypto.randomUUID();
    try {
      const payment = await apiRequest<Payment>(`bookings/${bookingId}/payment`, {
        method: "POST",
        headers: { "Idempotency-Key": paymentKey.current },
        body: jsonBody({}),
      });
      paymentKey.current = null;
      if (payment.provider !== "sandbox" || payment.checkout_url !== `/payments/sandbox/${payment.id}`) {
        throw new Error(workflowCopy.paymentLoadError);
      }
      router.push(payment.checkout_url);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : workflowCopy.paymentActionError);
    } finally {
      setPaymentBusy(false);
    }
  }

  async function blockParticipant() {
    if (!booking?.other_party_user_id) return;
    setBlockBusy(true);
    setError("");
    try {
      await apiRequest(`users/${booking.other_party_user_id}/block`, {
        method: "POST",
        body: jsonBody({}),
      });
      setBlocked(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : workflowCopy.bookingBlockError);
    } finally {
      setBlockBusy(false);
    }
  }

  async function safetyCheckIn(checkInStatus: "safe" | "needs_help") {
    if (!booking) return;
    setError("");
    setSafetyMessage("");
    try {
      await apiRequest(`bookings/${booking.id}/check-in`, {
        method: "POST",
        body: jsonBody({ status: checkInStatus }),
      });
      setSafetyMessage(workflowCopy.safetyCheckInSaved);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : workflowCopy.safetyCheckInError);
    }
  }

  async function submitSafetyReport(formData: FormData) {
    if (!booking) return;
    setReportBusy(true);
    setError("");
    try {
      await apiRequest("reports", {
        method: "POST",
        body: jsonBody({
          booking_id: booking.id,
          reason: formData.get("reason"),
          description: formData.get("description"),
        }),
      });
      setReportOpen(false);
      setSafetyMessage(workflowCopy.safetyReportSent);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : workflowCopy.safetyReportError);
    } finally {
      setReportBusy(false);
    }
  }

  async function submitReview(formData: FormData) {
    if (!booking) return;
    setError("");
    setReviewMessage("");
    try {
      await apiRequest(`bookings/${booking.id}/review`, {
        method: "POST",
        body: jsonBody({
          rating: Number(formData.get("rating")),
          comment: formData.get("comment"),
          private_safety_feedback: formData.get("private_safety_feedback"),
        }),
      });
      setReviewMessage(workflowCopy.reviewSent);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : workflowCopy.reviewError);
    }
  }

  const hostView = booking?.viewer_role === "host";
  const canCancel = booking && ["requested", "awaiting_payment", "confirmed"].includes(booking.status);

  return (
    <>
      <Nav />
      <main className="min-h-screen bg-[#F7F5F0] px-4 py-12 text-[#20201F] sm:px-6">
        <section className="mx-auto max-w-3xl rounded-3xl border border-[#E8E4DC] bg-white p-6 sm:p-9">
          <Link href={hostView ? "/dashboard/companion" : "/dashboard"} className="text-sm font-medium text-[#75404A]">
            {workflowCopy.bookingDashboardLink}
          </Link>
          <h1 className="mt-6 text-3xl font-semibold">{workflowCopy.bookingDetailTitle}</h1>
          {error ? <p role="alert" className="mt-5 rounded-xl bg-[#F7F5F0] p-4 text-sm text-red-700">{error}</p> : null}
          {!booking && !error ? <p className="mt-5 text-sm text-[#77736D]" aria-live="polite">{workflowCopy.bookingLoading}</p> : null}
          {booking ? (
            <>
              <div className="mt-6 flex flex-wrap items-start justify-between gap-4 border-b border-[#E8E4DC] pb-5">
                <div>
                  <h2 className="text-xl font-semibold">{booking.experience_title}</h2>
                  <p className="mt-1 text-sm text-[#77736D]">{workflowCopy.bookingWith} {booking.other_party}</p>
                </div>
                <span className="rounded-full bg-[#F7F5F0] px-3 py-1.5 text-sm capitalize">
                  {booking.status.replaceAll("_", " ")}
                </span>
              </div>
              <dl className="mt-5 grid gap-5 sm:grid-cols-2">
                <div>
                  <dt className="text-xs uppercase tracking-wide text-[#77736D]">{workflowCopy.bookingWhen}</dt>
                  <dd className="mt-1 text-sm">{new Intl.DateTimeFormat("en", {
                    dateStyle: "full",
                    timeStyle: "short",
                    timeZone: booking.timezone,
                  }).format(new Date(booking.start_at))}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-[#77736D]">{workflowCopy.bookingTotal}</dt>
                  <dd className="mt-1 text-sm font-medium">{formatPrice(booking.total_minor, booking.currency)}</dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-xs uppercase tracking-wide text-[#77736D]">{workflowCopy.bookingPublicVenue}</dt>
                  <dd className="mt-1 text-sm">{booking.public_venue_name}</dd>
                </div>
                {booking.customer_note ? (
                  <div className="sm:col-span-2">
                    <dt className="text-xs uppercase tracking-wide text-[#77736D]">{workflowCopy.bookingCustomerNote}</dt>
                    <dd className="mt-1 whitespace-pre-wrap text-sm">{booking.customer_note}</dd>
                  </div>
                ) : null}
              </dl>
              {booking.status === "awaiting_payment" ? (
                <p className="mt-6 rounded-xl bg-[#F7F5F0] p-4 text-sm leading-6 text-[#77736D]">
                  {booking.payment_deadline
                    ? `${workflowCopy.bookingHoldUntil} ${new Intl.DateTimeFormat("en", {
                      dateStyle: "short",
                      timeStyle: "short",
                      timeZone: booking.timezone,
                    }).format(new Date(booking.payment_deadline))}. `
                    : ""}
                  {workflowCopy.bookingPaymentLimitation}
                </p>
              ) : null}
              {booking.status === "confirmed" ? (
                <p role="status" className="mt-6 rounded-xl bg-[#F7F5F0] p-4 text-sm text-[#526044]">
                  {workflowCopy.bookingConfirmSuccess}
                </p>
              ) : null}
              <div className="mt-6 flex flex-wrap gap-3">
                {!hostView && booking.status === "awaiting_payment" ? (
                  <button type="button" disabled={paymentBusy} onClick={() => void pay()} className="h-11 rounded-full bg-[#75404A] px-5 text-sm font-medium text-white disabled:opacity-50">
                    {paymentBusy ? workflowCopy.paymentLoading : workflowCopy.bookingPayNow}
                  </button>
                ) : null}
                {hostView && booking.status === "requested" ? (
                  <>
                    <button type="button" disabled={busy} onClick={() => void act("accept")} className="h-11 rounded-full bg-[#75404A] px-5 text-sm font-medium text-white disabled:opacity-50">{workflowCopy.bookingAccept}</button>
                    <button type="button" disabled={busy} onClick={() => void act("decline")} className="h-11 rounded-full border border-[#E8E4DC] px-5 text-sm disabled:opacity-50">{workflowCopy.bookingDecline}</button>
                  </>
                ) : null}
                {hostView && booking.status === "confirmed" ? (
                  <button type="button" disabled={busy} onClick={() => void act("start")} className="h-11 rounded-full bg-[#75404A] px-5 text-sm font-medium text-white disabled:opacity-50">{workflowCopy.bookingStart}</button>
                ) : null}
                {hostView && booking.status === "in_progress" ? (
                  <button type="button" disabled={busy} onClick={() => void act("complete")} className="h-11 rounded-full bg-[#75404A] px-5 text-sm font-medium text-white disabled:opacity-50">{workflowCopy.bookingComplete}</button>
                ) : null}
                {canCancel ? (
                  <button type="button" disabled={busy} onClick={() => void act("cancel")} className="h-11 rounded-full border border-[#E8E4DC] px-5 text-sm text-[#75404A] disabled:opacity-50">{workflowCopy.bookingCancel}</button>
                ) : null}
                {booking.other_party_user_id && !blocked ? (
                  <button type="button" disabled={blockBusy} onClick={() => void blockParticipant()} className="h-11 rounded-full border border-[#E8E4DC] px-5 text-sm text-[#75404A] disabled:opacity-50">
                    {blockBusy ? workflowCopy.messageSending : workflowCopy.bookingBlockParticipant}
                  </button>
                ) : null}
                {blocked ? <span role="status" className="self-center text-sm text-[#77736D]">{workflowCopy.bookingBlocked}</span> : null}
                {booking.other_party_user_id && !reportOpen ? (
                  <button type="button" onClick={() => setReportOpen(true)} className="h-11 rounded-full border border-[#E8E4DC] px-5 text-sm text-[#75404A]">
                    {workflowCopy.safetyReportAction}
                  </button>
                ) : null}
              </div>
              {reportOpen ? (
                <form action={(formData) => void submitSafetyReport(formData)} className="mt-5 space-y-3 rounded-2xl border border-[#E8E4DC] bg-[#F7F5F0] p-5">
                  <label className="block text-sm font-medium">
                    {workflowCopy.safetyReportReason}
                    <select name="reason" required className="mt-2 h-11 w-full rounded-lg border border-[#E8E4DC] bg-white px-3">
                      <option value="safety_concern">{workflowCopy.safetyReasonSafetyConcern}</option>
                        <option value="harassment">{workflowCopy.safetyReasonHarassment}</option>
                        <option value="misconduct">{workflowCopy.safetyReasonMisconduct}</option>
                        <option value="no_show">{workflowCopy.safetyReasonNoShow}</option>
                        <option value="impersonation">{workflowCopy.safetyReasonImpersonation}</option>
                        <option value="other">{workflowCopy.safetyReasonOther}</option>
                    </select>
                  </label>
                  <label className="block text-sm font-medium">
                    {workflowCopy.safetyReportDescription}
                    <textarea name="description" required maxLength={5000} className="mt-2 min-h-28 w-full rounded-lg border border-[#E8E4DC] bg-white p-3" />
                  </label>
                  <div className="flex gap-2">
                    <button disabled={reportBusy} className="rounded-full bg-[#75404A] px-4 py-2 text-sm text-white disabled:opacity-60">{reportBusy ? workflowCopy.messageSending : workflowCopy.safetyReportSubmit}</button>
                    <button type="button" onClick={() => setReportOpen(false)} className="rounded-full border border-[#E8E4DC] px-4 py-2 text-sm">{workflowCopy.safetyReportCancel}</button>
                  </div>
                </form>
              ) : null}
              {["confirmed", "in_progress"].includes(booking.status) ? (
                <section className="mt-7 rounded-2xl border border-[#E8E4DC] bg-[#F7F5F0] p-5">
                  <h2 className="text-lg font-semibold">{workflowCopy.safetyCheckInTitle}</h2>
                  <p className="mt-1 text-sm text-[#77736D]">{workflowCopy.safetyCheckInDescription}</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button type="button" onClick={() => void safetyCheckIn("safe")} className="rounded-full bg-[#777B61] px-4 py-2 text-sm text-white">{workflowCopy.safetyCheckInSafe}</button>
                    <button type="button" onClick={() => void safetyCheckIn("needs_help")} className="rounded-full border border-[#75404A] px-4 py-2 text-sm text-[#75404A]">{workflowCopy.safetyCheckInHelp}</button>
                  </div>
                  {safetyMessage ? <p role="status" className="mt-3 text-sm text-[#526044]">{safetyMessage}</p> : null}
                </section>
              ) : null}
              {!hostView && booking.status === "completed" ? (
                <section className="mt-7 rounded-2xl border border-[#E8E4DC] bg-white p-5">
                  <h2 className="text-lg font-semibold">{workflowCopy.reviewTitle}</h2>
                  {reviewMessage ? <p role="status" className="mt-3 text-sm text-[#526044]">{reviewMessage}</p> : (
                    <form action={(formData) => void submitReview(formData)} className="mt-4 space-y-3">
                      <label className="block text-sm font-medium">{workflowCopy.reviewRating}
                        <select name="rating" required className="mt-2 h-11 w-full rounded-lg border border-[#E8E4DC] bg-white px-3">
                          {[5, 4, 3, 2, 1].map((rating) => <option key={rating} value={rating}>{rating}/5</option>)}
                        </select>
                      </label>
                      <label className="block text-sm font-medium">{workflowCopy.reviewComment}
                        <textarea name="comment" maxLength={2000} className="mt-2 min-h-24 w-full rounded-lg border border-[#E8E4DC] p-3" />
                      </label>
                      <label className="block text-sm font-medium">{workflowCopy.reviewPrivateFeedback}
                        <textarea name="private_safety_feedback" maxLength={2000} className="mt-2 min-h-24 w-full rounded-lg border border-[#E8E4DC] p-3" />
                      </label>
                      <button className="rounded-full bg-[#75404A] px-5 py-3 text-sm text-white">{workflowCopy.reviewSubmit}</button>
                      <p className="text-xs text-[#77736D]">{workflowCopy.reviewVerifiedNote}</p>
                    </form>
                  )}
                </section>
              ) : null}
              {booking.conversation_id ? <ConversationPanel conversationId={booking.conversation_id} /> : null}
              <section className="mt-9 border-t border-[#E8E4DC] pt-6">
                <h2 className="text-lg font-semibold">{workflowCopy.bookingActivity}</h2>
                {events.length ? (
                  <ol className="mt-4 space-y-3">
                    {events.map((event, index) => (
                      <li key={`${event.event_type}-${event.created_at}-${index}`} className="flex items-start justify-between gap-3 text-sm">
                        <span className="capitalize text-[#20201F]">{event.event_type.replaceAll("_", " ")}{event.new_state ? ` · ${event.new_state.replaceAll("_", " ")}` : ""}</span>
                        <time className="shrink-0 text-xs text-[#77736D]" dateTime={event.created_at}>{new Intl.DateTimeFormat("en", {
                          dateStyle: "short",
                          timeStyle: "short",
                          timeZone: booking.timezone,
                        }).format(new Date(event.created_at))}</time>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="mt-3 text-sm text-[#77736D]">{workflowCopy.bookingNoEvents}</p>
                )}
              </section>
            </>
          ) : null}
        </section>
      </main>
    </>
  );
}
