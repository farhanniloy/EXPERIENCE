"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Nav } from "@/components/layout/nav";
import { ApiError, apiRequest } from "@/lib/api-client";
import { formatPrice } from "@/lib/public-data";
import { siteConfig } from "@/lib/site-config";
import { workflowCopy } from "@/lib/workflow-copy";

type Booking = {
  id: string;
  status: string;
  start_at: string;
  end_at: string;
  experience_title: string;
  other_party: string;
  total_minor: number;
  currency: string;
};
type DashboardData = { display_name: string; bookings: Booking[] };

export function CustomerDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiRequest<DashboardData>("dashboard")
      .then(setData)
      .catch((reason: unknown) => setError(
        reason instanceof ApiError && reason.status === 403
          ? "Sign in to see your plans."
          : reason instanceof Error ? reason.message : "Could not load your plans.",
      ));
  }, []);

  return (
    <>
      <Nav />
      <main className="min-h-screen bg-[#F7F5F0] px-4 py-12 text-[#20201F] sm:px-6">
        <div className="mx-auto max-w-5xl">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">Customer dashboard</p>
          <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
            <h1 className="text-3xl font-semibold">{workflowCopy.customerDashboardTitle}</h1>
            <Link href="/messages" className="text-sm font-medium text-[#75404A]">{workflowCopy.messagesInboxTitle}</Link>
          </div>
          {data ? <p className="mt-2 text-sm text-[#77736D]">Welcome, {data.display_name || "there"}.</p> : null}
          {error ? (
            <section className="mt-8 rounded-2xl border border-[#E8E4DC] bg-white p-6">
              <p role="alert" className="text-sm text-red-700">{error}</p>
              <Link href="/login" className="mt-4 inline-flex text-sm font-medium text-[#75404A]">Sign in</Link>
            </section>
          ) : !data ? (
            <p className="mt-8 text-sm text-[#77736D]" aria-live="polite">Loading your plans…</p>
          ) : data.bookings.length === 0 ? (
            <section className="mt-8 rounded-2xl border border-[#E8E4DC] bg-white p-8">
              <p className="text-sm text-[#77736D]">{workflowCopy.noBookings}</p>
              <Link href="/explore" className="mt-5 inline-flex rounded-full bg-[#75404A] px-5 py-3 text-sm font-medium text-white">Explore experiences</Link>
            </section>
          ) : (
            <div className="mt-8 space-y-3">
              {data.bookings.map((booking) => (
                <article key={booking.id} className="grid gap-3 rounded-2xl border border-[#E8E4DC] bg-white p-5 sm:grid-cols-[1fr_auto] sm:items-center">
                  <div>
                    <Link href={`/bookings/${booking.id}`} className="font-semibold text-[#75404A]">{booking.experience_title}</Link>
                    <p className="mt-1 text-sm text-[#77736D]">With {booking.other_party} · {new Intl.DateTimeFormat("en", {
                      dateStyle: "medium",
                      timeStyle: "short",
                      timeZone: siteConfig.timezone,
                    }).format(new Date(booking.start_at))}</p>
                  </div>
                  <div className="text-sm sm:text-right">
                    <p className="font-medium">{formatPrice(booking.total_minor, booking.currency)}</p>
                    <p className="mt-1 capitalize text-[#77736D]">{booking.status.replaceAll("_", " ")}</p>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </main>
    </>
  );
}
