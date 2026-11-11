"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Nav } from "@/components/layout/nav";
import { ApiError, apiRequest } from "@/lib/api-client";
import { formatPrice } from "@/lib/public-data";
import { workflowCopy } from "@/lib/workflow-copy";

type Host = {
  display_name: string;
  status: string;
  adult_confirmed: boolean;
  verification_provider: string | null;
};
type Experience = {
  id: string;
  title: string;
  status: string;
  price_minor: number;
  currency: string;
};
type Booking = {
  id: string;
  status: string;
  start_at: string;
  experience_title: string;
  other_party: string;
  total_minor: number;
  currency: string;
};
type DashboardData = { host: Host; experiences: Experience[]; bookings: Booking[] };

export function HostDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiRequest<DashboardData>("dashboard/companion")
      .then(setData)
      .catch((reason: unknown) => setError(
        reason instanceof ApiError && reason.status === 403
          ? "Sign in to view your host dashboard."
          : reason instanceof Error ? reason.message : "Could not load the host dashboard.",
      ));
  }, []);

  return (
    <>
      <Nav />
      <main className="min-h-screen bg-[#F7F5F0] px-4 py-12 text-[#20201F] sm:px-6">
        <div className="mx-auto max-w-5xl">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">Along · Host</p>
          <h1 className="mt-3 text-3xl font-semibold">{workflowCopy.hostDashboardTitle}</h1>
          {error ? (
            <section className="mt-8 rounded-2xl border border-[#E8E4DC] bg-white p-6">
              <p role="alert" className="text-sm text-red-700">{error}</p>
              <Link href="/login" className="mt-4 inline-flex text-sm font-medium text-[#75404A]">Sign in</Link>
            </section>
          ) : !data ? (
            <p className="mt-8 text-sm text-[#77736D]" aria-live="polite">Loading host dashboard…</p>
          ) : (
            <>
              <section className="mt-8 flex flex-wrap items-center justify-between gap-5 rounded-2xl border border-[#E8E4DC] bg-white p-6">
                <div>
                  <h2 className="text-lg font-semibold">{data.host.display_name || "Your host profile"}</h2>
                  <p className="mt-1 text-sm capitalize text-[#77736D]">Application: {data.host.status.replaceAll("_", " ")}</p>
                  {data.host.verification_provider === "development_mock" ? (
                    <p className="mt-2 text-xs text-[#77736D]">{workflowCopy.developmentAdapter} · not identity verification</p>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-3">
                  <Link href="/become-a-companion" className="rounded-full border border-[#E8E4DC] px-5 py-3 text-sm font-medium">Edit profile</Link>
                  <Link href="/dashboard/companion/experiences/new" className="rounded-full bg-[#75404A] px-5 py-3 text-sm font-medium text-white">Create experience</Link>
                </div>
              </section>

              {data.host.status !== "approved" ? (
                <p className="mt-4 rounded-xl bg-[#EFE9E2] p-4 text-sm leading-6 text-[#62373d]">
                  {data.host.status === "draft"
                    ? "Complete host onboarding and submit your profile for review. You can save experience drafts while you wait."
                    : "Your profile is in review. Experience publishing unlocks after approval."}
                </p>
              ) : null}

              <section className="mt-10">
                <div className="flex items-end justify-between">
                  <h2 className="text-xl font-semibold">Your experiences</h2>
                  <Link href="/dashboard/companion/experiences/new" className="text-sm font-medium text-[#75404A]">Add experience</Link>
                </div>
                {data.experiences.length === 0 ? (
                  <p className="mt-4 rounded-2xl border border-[#E8E4DC] bg-white p-6 text-sm text-[#77736D]">{workflowCopy.noExperiences}</p>
                ) : (
                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    {data.experiences.map((experience) => (
                      <article key={experience.id} className="flex items-start justify-between gap-4 rounded-2xl border border-[#E8E4DC] bg-white p-5">
                        <div>
                          <h3 className="font-semibold">{experience.title}</h3>
                          <p className="mt-1 text-sm text-[#77736D]">{formatPrice(experience.price_minor, experience.currency)}</p>
                        </div>
                        <div className="text-right">
                          <p className="text-xs capitalize text-[#77736D]">{experience.status.replaceAll("_", " ")}</p>
                          <Link href={`/dashboard/companion/experiences/${experience.id}/edit`} className="mt-3 inline-flex text-sm font-medium text-[#75404A]">Edit</Link>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </section>

              <section className="mt-10">
                <h2 className="text-xl font-semibold">Bookings</h2>
                {data.bookings.length === 0 ? (
                  <p className="mt-4 rounded-2xl border border-[#E8E4DC] bg-white p-6 text-sm text-[#77736D]">{workflowCopy.noBookings}</p>
                ) : (
                  <div className="mt-4 space-y-3">
                    {data.bookings.map((booking) => (
                      <article key={booking.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#E8E4DC] bg-white p-5">
                        <div>
                          <h3 className="font-medium">{booking.experience_title}</h3>
                          <p className="mt-1 text-sm text-[#77736D]">With {booking.other_party} · {new Date(booking.start_at).toLocaleString()}</p>
                        </div>
                        <div className="text-sm sm:text-right">
                          <p>{formatPrice(booking.total_minor, booking.currency)}</p>
                          <p className="mt-1 capitalize text-[#77736D]">{booking.status.replaceAll("_", " ")}</p>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      </main>
    </>
  );
}
