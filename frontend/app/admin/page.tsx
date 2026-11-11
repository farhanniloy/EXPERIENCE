"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Nav } from "@/components/layout/nav";
import { ApiError, apiRequest, jsonBody } from "@/lib/api-client";
import { formatPrice } from "@/lib/currency";
import { workflowCopy } from "@/lib/workflow-copy";

type Report = {
  id: string;
  reporter: string;
  reported: string;
  booking_id: string | null;
  experience_title: string;
  reason: string;
  description: string;
  status: string;
  created_at: string;
  incident_status: string;
};

type Review = {
  id: string;
  booking_id: string;
  experience_title: string;
  reviewer: string;
  host: string;
  rating: number;
  comment: string;
  private_safety_feedback: string;
  status: string;
  verified_booking: boolean;
  created_at: string;
};

type Booking = {
  id: string;
  experience_title: string;
  customer: string;
  host: string;
  status: string;
  start_at: string;
  total_minor: number;
  currency: string;
};

type Payment = {
  id: string;
  booking_id: string;
  provider: string;
  status: string;
  amount_minor: number;
  currency: string;
  created_at: string;
};

type Dashboard = {
  counts: Record<string, number>;
  can_suspend_accounts: boolean;
  bookings: Booking[];
  payments: Payment[];
  reports: Report[];
  reviews: Review[];
  audit_log_count: number;
};

export default function AdminPage() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      setDashboard(await apiRequest<Dashboard>("admin/dashboard"));
      setError("");
    } catch (reason) {
      setError(
        reason instanceof ApiError && reason.status === 403
          ? workflowCopy.adminAccessDenied
          : reason instanceof Error ? reason.message : workflowCopy.adminLoadError,
      );
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function actOnReport(report: Report, action: "review" | "resolve" | "dismiss" | "suspend") {
    setBusy(report.id);
    setError("");
    try {
      await apiRequest(`admin/reports/${report.id}`, {
        method: "POST",
        body: jsonBody({ action }),
      });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not update this report.");
    } finally {
      setBusy("");
    }
  }

  async function moderateReview(review: Review, action: "approve" | "reject") {
    setBusy(review.id);
    setError("");
    try {
      await apiRequest(`admin/reviews/${review.id}`, {
        method: "POST",
        body: jsonBody({ action }),
      });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not moderate this review.");
    } finally {
      setBusy("");
    }
  }

  return (
    <>
      <Nav />
      <main className="min-h-screen bg-[#F7F5F0] px-4 py-12 text-[#20201F] sm:px-6">
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">{workflowCopy.adminStaffWorkspace}</p>
              <h1 className="mt-3 text-3xl font-semibold">{workflowCopy.adminTitle}</h1>
              <p className="mt-2 text-sm text-[#77736D]">{workflowCopy.adminIntro}</p>
            </div>
            <Link href="/admin/moderation" className="rounded-full border border-[#E8E4DC] bg-white px-5 py-3 text-sm font-medium">
              {workflowCopy.adminModerationLink}
            </Link>
          </div>
          {error ? <p role="alert" className="mt-6 rounded-xl bg-white p-4 text-sm text-red-700">{error}</p> : null}
          {!dashboard && !error ? <p className="mt-8 text-sm text-[#77736D]">{workflowCopy.adminLoading}</p> : null}
          {dashboard ? (
            <>
              <section aria-label="Platform overview" className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(dashboard.counts).map(([key, count]) => (
                  <article key={key} className="rounded-2xl border border-[#E8E4DC] bg-white p-5">
                    <p className="text-sm text-[#77736D]">{workflowCopy.adminCountLabel(key)}</p>
                    <p className="mt-2 text-2xl font-semibold">{count}</p>
                  </article>
                ))}
                <article className="rounded-2xl border border-[#E8E4DC] bg-white p-5">
                  <p className="text-sm text-[#77736D]">{workflowCopy.adminAuditCounter}</p>
                  <p className="mt-2 text-2xl font-semibold">{dashboard.audit_log_count}</p>
                </article>
              </section>

              <section className="mt-10">
                <h2 className="text-2xl font-semibold">{workflowCopy.adminReportsTitle}</h2>
                {dashboard.reports.length === 0 ? <p className="mt-4 rounded-xl border border-[#E8E4DC] bg-white p-5 text-sm text-[#77736D]">{workflowCopy.adminNoReports}</p> : (
                  <div className="mt-4 space-y-3">
                    {dashboard.reports.map((report) => (
                      <article key={report.id} className="rounded-2xl border border-[#E8E4DC] bg-white p-5">
                        <div className="flex flex-wrap justify-between gap-3">
                          <div>
                            <h3 className="font-semibold">{report.reason.replaceAll("_", " ")} · {report.status.replaceAll("_", " ")}</h3>
                            <p className="mt-1 text-sm text-[#77736D]">{workflowCopy.adminReportedBy(report.reporter, report.reported)}</p>
                            {report.experience_title ? <p className="mt-1 text-sm text-[#77736D]">{report.experience_title}</p> : null}
                          </div>
                          <time className="text-xs text-[#77736D]">{new Date(report.created_at).toLocaleString()}</time>
                        </div>
                        <p className="mt-4 whitespace-pre-wrap text-sm leading-6">{report.description}</p>
                        <div className="mt-4 flex flex-wrap gap-2">
                          {report.status === "open" ? (
                            <button disabled={busy === report.id} onClick={() => void actOnReport(report, "review")} className="rounded-full bg-[#75404A] px-4 py-2 text-sm text-white disabled:opacity-60">{workflowCopy.adminAssign}</button>
                          ) : null}
                          {report.status !== "resolved" && report.status !== "dismissed" ? (
                            <button disabled={busy === report.id} onClick={() => void actOnReport(report, "resolve")} className="rounded-full border border-[#E8E4DC] px-4 py-2 text-sm disabled:opacity-60">{workflowCopy.adminResolve}</button>
                          ) : null}
                          {report.status !== "resolved" && report.status !== "dismissed" ? (
                            <button disabled={busy === report.id} onClick={() => void actOnReport(report, "dismiss")} className="rounded-full border border-[#E8E4DC] px-4 py-2 text-sm disabled:opacity-60">{workflowCopy.adminDismiss}</button>
                          ) : null}
                          {dashboard.can_suspend_accounts && report.status !== "resolved" && report.status !== "dismissed" ? (
                            <button disabled={busy === report.id} onClick={() => void actOnReport(report, "suspend")} className="rounded-full border border-red-200 px-4 py-2 text-sm text-red-800 disabled:opacity-60">{workflowCopy.adminSuspend}</button>
                          ) : null}
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </section>

              <section className="mt-10">
                <h2 className="text-2xl font-semibold">{workflowCopy.adminReviewsTitle}</h2>
                {dashboard.reviews.filter((review) => review.status === "pending").length === 0 ? <p className="mt-4 rounded-xl border border-[#E8E4DC] bg-white p-5 text-sm text-[#77736D]">{workflowCopy.adminNoReviews}</p> : (
                  <div className="mt-4 space-y-3">
                    {dashboard.reviews.filter((review) => review.status === "pending").map((review) => (
                      <article key={review.id} className="rounded-2xl border border-[#E8E4DC] bg-white p-5">
                        <h3 className="font-semibold">{review.experience_title} · {review.rating}/5</h3>
                        <p className="mt-1 text-sm text-[#77736D]">{workflowCopy.adminVerifiedBooking(review.reviewer, review.host)}</p>
                        {review.comment ? <p className="mt-3 text-sm">{review.comment}</p> : null}
                        {review.private_safety_feedback ? <p className="mt-3 rounded-lg bg-[#F7F5F0] p-3 text-sm">{workflowCopy.adminPrivateFeedback(review.private_safety_feedback)}</p> : null}
                        <div className="mt-4 flex gap-2">
                          <button disabled={busy === review.id} onClick={() => void moderateReview(review, "approve")} className="rounded-full bg-[#75404A] px-4 py-2 text-sm text-white disabled:opacity-60">{workflowCopy.adminPublishReview}</button>
                          <button disabled={busy === review.id} onClick={() => void moderateReview(review, "reject")} className="rounded-full border border-[#E8E4DC] px-4 py-2 text-sm disabled:opacity-60">{workflowCopy.adminRejectReview}</button>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </section>

              <section className="mt-10 grid gap-8 xl:grid-cols-2">
                <div>
                  <h2 className="text-2xl font-semibold">{workflowCopy.adminBookingsTitle}</h2>
                  <div className="mt-4 overflow-x-auto rounded-2xl border border-[#E8E4DC] bg-white">
                    <table className="w-full text-left text-sm">
                      <thead className="border-b border-[#E8E4DC] text-[#77736D]"><tr><th className="p-3">{workflowCopy.adminBookingColumn}</th><th className="p-3">{workflowCopy.adminBookingParties}</th><th className="p-3">{workflowCopy.adminStatusColumn}</th></tr></thead>
                      <tbody>{dashboard.bookings.length ? dashboard.bookings.map((booking) => <tr key={booking.id} className="border-b border-[#E8E4DC] last:border-0"><td className="p-3">{booking.experience_title}</td><td className="p-3">{booking.customer} / {booking.host}</td><td className="p-3">{booking.status.replaceAll("_", " ")}</td></tr>) : <tr><td className="p-3 text-[#77736D]" colSpan={3}>{workflowCopy.adminNoBookings}</td></tr>}</tbody>
                    </table>
                  </div>
                </div>
                <div>
                  <h2 className="text-2xl font-semibold">{workflowCopy.adminPaymentsTitle}</h2>
                  <div className="mt-4 overflow-x-auto rounded-2xl border border-[#E8E4DC] bg-white">
                    <table className="w-full text-left text-sm">
                      <thead className="border-b border-[#E8E4DC] text-[#77736D]"><tr><th className="p-3">{workflowCopy.adminProviderColumn}</th><th className="p-3">{workflowCopy.adminAmountColumn}</th><th className="p-3">{workflowCopy.adminStatusColumn}</th></tr></thead>
                      <tbody>{dashboard.payments.length ? dashboard.payments.map((payment) => <tr key={payment.id} className="border-b border-[#E8E4DC] last:border-0"><td className="p-3">{payment.provider}</td><td className="p-3">{formatPrice(payment.amount_minor, payment.currency)}</td><td className="p-3">{payment.status}</td></tr>) : <tr><td className="p-3 text-[#77736D]" colSpan={3}>{workflowCopy.adminNoPayments}</td></tr>}</tbody>
                    </table>
                  </div>
                </div>
              </section>
            </>
          ) : null}
        </div>
      </main>
    </>
  );
}
