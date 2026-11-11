"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Footer } from "@/components/layout/footer";
import { Nav } from "@/components/layout/nav";
import { ApiError, apiRequest, jsonBody } from "@/lib/api-client";
import { Experience, fetchPublicMarketplaceData, formatPrice } from "@/lib/public-data";
import { siteConfig } from "@/lib/site-config";
import { workflowCopy } from "@/lib/workflow-copy";

type Slot = { start_at: string; end_at: string; timezone: string };
type Booking = { id: string };

function localDateAfter(days: number) {
  const parts = new Intl.DateTimeFormat("en", {
    timeZone: siteConfig.timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const value = (type: string) => Number(parts.find((part) => part.type === type)?.value);
  const date = new Date(Date.UTC(value("year"), value("month") - 1, value("day") + days));
  return date.toISOString().slice(0, 10);
}

export function BookingFlow({ slug }: { slug: string }) {
  const router = useRouter();
  const [experience, setExperience] = useState<Experience | null>(null);
  const [loadError, setLoadError] = useState("");
  const [date, setDate] = useState(() => localDateAfter(7));
  const [duration, setDuration] = useState(60);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [selectedStart, setSelectedStart] = useState("");
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [slotError, setSlotError] = useState("");
  const [publicVenue, setPublicVenue] = useState("");
  const [customerNote, setCustomerNote] = useState("");
  const [confirmedAdult, setConfirmedAdult] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const keyState = useRef<{ payload: string; key: string } | null>(null);

  useEffect(() => {
    let active = true;
    fetchPublicMarketplaceData()
      .then((data) => {
        if (!active) return;
        const found = data.experiences.find((item) => item.slug === slug);
        if (!found) {
          setLoadError(workflowCopy.bookingExperienceNotFound);
          return;
        }
        setExperience(found);
        setDuration(found.duration_minutes);
      })
      .catch((reason: unknown) => {
        if (active) {
          setLoadError(reason instanceof Error ? reason.message : workflowCopy.bookingExperienceLoadError);
        }
      });
    return () => { active = false; };
  }, [slug]);

  const durationOptions = useMemo(() => {
    if (!experience) return [];
    const minimum = experience.min_duration_minutes ?? experience.duration_minutes;
    const maximum = experience.max_duration_minutes ?? experience.duration_minutes;
    const values = new Set([minimum, experience.duration_minutes, maximum]);
    return [...values].filter((value) => value >= minimum && value <= maximum).sort((a, b) => a - b);
  }, [experience]);

  const loadSlots = useCallback(async () => {
    if (!experience || !date) return;
    setSlotsLoading(true);
    setSlotError("");
    setSelectedStart("");
    try {
      const params = new URLSearchParams({
        from: date,
        to: date,
        duration_minutes: String(duration),
        timezone: siteConfig.timezone,
      });
      const result = await apiRequest<Slot[]>(
        `experiences/${encodeURIComponent(experience.slug)}/availability?${params.toString()}`,
      );
      setSlots(result);
    } catch (reason) {
      setSlots([]);
      setSlotError(reason instanceof Error ? reason.message : workflowCopy.bookingAvailabilityError);
    } finally {
      setSlotsLoading(false);
    }
  }, [date, duration, experience]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadSlots(); }, 0);
    return () => window.clearTimeout(timer);
  }, [loadSlots]);

  async function submitBooking() {
    if (!experience || !selectedStart) return;
    setSubmitError("");
    if (!confirmedAdult) {
      setSubmitError(workflowCopy.bookingAdultRequired);
      return;
    }
    if (!publicVenue.trim()) {
      setSubmitError(workflowCopy.bookingVenueRequired);
      return;
    }
    const payload = {
      experience_id: experience.id,
      start_at: selectedStart,
      duration_minutes: duration,
      booking_mode: experience.instant_book ? "instant" : "request",
      timezone: siteConfig.timezone,
      public_venue_name: publicVenue.trim(),
      customer_note: customerNote.trim(),
    };
    const payloadText = JSON.stringify(payload);
    if (!keyState.current || keyState.current.payload !== payloadText) {
      keyState.current = { payload: payloadText, key: crypto.randomUUID() };
    }
    setSubmitting(true);
    try {
      await apiRequest("companions/me/verification", {
        method: "POST",
        body: jsonBody({ confirmed_18: true }),
      });
      const booking = await apiRequest<Booking>("bookings", {
        method: "POST",
        headers: { "Idempotency-Key": keyState.current.key },
        body: jsonBody(payload),
      });
      router.push(`/bookings/${booking.id}`);
    } catch (reason) {
      setSubmitError(
        reason instanceof ApiError && reason.status === 403
          ? workflowCopy.bookingAuthOrVerificationError
          : reason instanceof Error ? reason.message : workflowCopy.bookingCreateError,
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Nav />
      <main className="min-h-screen bg-[#F7F5F0] px-4 py-12 text-[#20201F] sm:px-6">
        <section className="mx-auto max-w-3xl rounded-3xl border border-[#E8E4DC] bg-white p-6 sm:p-9">
          <Link href={`/experiences/${slug}`} className="text-sm font-medium text-[#75404A]">
            {workflowCopy.bookingBackToExperience}
          </Link>
          <h1 className="mt-6 text-3xl font-semibold">{workflowCopy.bookingTitle}</h1>
          {loadError ? <p role="alert" className="mt-5 text-sm text-red-700">{loadError}</p> : null}
          {!experience && !loadError ? (
            <p className="mt-5 text-sm text-[#77736D]" aria-live="polite">{workflowCopy.bookingLoading}</p>
          ) : null}
          {experience ? (
            <>
              <div className="mt-5 rounded-2xl bg-[#F7F5F0] p-5">
                <h2 className="font-semibold">{experience.title}</h2>
                <p className="mt-1 text-sm text-[#77736D]">{experience.host_name} · {experience.city}</p>
                <p className="mt-3 font-medium">{formatPrice(experience.price_minor, experience.currency)}</p>
              </div>
              <div className="mt-7 grid gap-5 sm:grid-cols-2">
                <label className="block text-sm font-medium">
                  {workflowCopy.bookingDateLabel}
                  <input
                    className="mt-2 h-12 w-full rounded-xl border border-[#E8E4DC] bg-white px-4 font-normal"
                    type="date"
                    min={localDateAfter(0)}
                    value={date}
                    onChange={(event) => setDate(event.target.value)}
                  />
                </label>
                {durationOptions.length > 1 ? (
                  <label className="block text-sm font-medium">
                    {workflowCopy.bookingDurationLabel}
                    <select
                      className="mt-2 h-12 w-full rounded-xl border border-[#E8E4DC] bg-white px-4 font-normal"
                      value={duration}
                      onChange={(event) => setDuration(Number(event.target.value))}
                    >
                      {durationOptions.map((minutes) => (
                        <option key={minutes} value={minutes}>{workflowCopy.bookingDurationOption(minutes)}</option>
                      ))}
                    </select>
                  </label>
                ) : null}
              </div>
              <section className="mt-7" aria-live="polite">
                <h2 className="text-sm font-semibold">{workflowCopy.bookingChooseTime}</h2>
                {slotsLoading ? <p className="mt-3 text-sm text-[#77736D]">{workflowCopy.bookingSlotsLoading}</p> : null}
                {slotError ? <p role="alert" className="mt-3 text-sm text-red-700">{slotError}</p> : null}
                {!slotsLoading && !slotError && slots.length === 0 ? (
                  <p className="mt-3 text-sm text-[#77736D]">{workflowCopy.bookingNoSlots}</p>
                ) : null}
                <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {slots.map((slot) => (
                    <button
                      key={slot.start_at}
                      type="button"
                      aria-pressed={selectedStart === slot.start_at}
                      onClick={() => setSelectedStart(slot.start_at)}
                      className={`rounded-xl border px-3 py-3 text-sm ${selectedStart === slot.start_at ? "border-[#75404A] bg-[#75404A] text-white" : "border-[#E8E4DC] bg-white text-[#20201F]"}`}
                    >
                      {new Intl.DateTimeFormat("en", {
                        timeZone: siteConfig.timezone,
                        hour: "numeric",
                        minute: "2-digit",
                      }).format(new Date(slot.start_at))}
                    </button>
                  ))}
                </div>
              </section>
              <label className="mt-7 block text-sm font-medium">
                {workflowCopy.bookingVenueLabel}
                <input
                  required
                  maxLength={180}
                  className="mt-2 h-12 w-full rounded-xl border border-[#E8E4DC] bg-white px-4 font-normal"
                  placeholder={workflowCopy.bookingVenuePlaceholder}
                  value={publicVenue}
                  onChange={(event) => setPublicVenue(event.target.value)}
                />
                <span className="mt-1 block text-xs font-normal text-[#77736D]">{workflowCopy.bookingVenueHelp}</span>
              </label>
              <label className="mt-5 block text-sm font-medium">
                {workflowCopy.bookingNoteLabel}
                <textarea
                  maxLength={2000}
                  rows={3}
                  className="mt-2 w-full rounded-xl border border-[#E8E4DC] bg-white px-4 py-3 font-normal"
                  value={customerNote}
                  onChange={(event) => setCustomerNote(event.target.value)}
                />
              </label>
              <label className="mt-5 flex items-start gap-3 text-sm leading-6">
                <input
                  type="checkbox"
                  className="mt-1 accent-[#75404A]"
                  checked={confirmedAdult}
                  onChange={(event) => setConfirmedAdult(event.target.checked)}
                />
                {workflowCopy.bookingAdultConfirmation}
              </label>
              <p className="mt-3 text-xs leading-5 text-[#77736D]">{workflowCopy.bookingDevelopmentVerification}</p>
              {submitError ? <p role="alert" className="mt-4 text-sm text-red-700">{submitError}</p> : null}
              <button
                type="button"
                disabled={!selectedStart || !publicVenue.trim() || !confirmedAdult || submitting}
                onClick={() => void submitBooking()}
                className="mt-6 h-12 rounded-full bg-[#75404A] px-6 text-sm font-medium text-white disabled:opacity-50"
              >
                {submitting ? workflowCopy.bookingSubmitting : experience.instant_book ? workflowCopy.bookingInstantAction : workflowCopy.bookingRequestAction}
              </button>
            </>
          ) : null}
        </section>
      </main>
      <Footer />
    </>
  );
}
