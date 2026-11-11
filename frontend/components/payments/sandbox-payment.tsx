"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Nav } from "@/components/layout/nav";
import { ApiError, apiRequest, jsonBody } from "@/lib/api-client";
import { formatPrice } from "@/lib/currency";
import { workflowCopy } from "@/lib/workflow-copy";

type Payment = {
  id: string;
  booking_id: string;
  booking_status: string;
  status: string;
  provider: string;
  provider_label: string;
  amount_minor: number;
  currency: string;
};
type Outcome = "success" | "failure" | "expiry";

export function SandboxPayment({ paymentId }: { paymentId: string }) {
  const router = useRouter();
  const [payment, setPayment] = useState<Payment | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const current = await apiRequest<Payment>(`payments/${paymentId}`);
      setPayment(current);
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiError && reason.status === 404
        ? workflowCopy.paymentLoadError
        : reason instanceof Error ? reason.message : workflowCopy.paymentLoadError);
    }
  }, [paymentId]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function complete(outcome: Outcome) {
    setBusy(true);
    setError("");
    try {
      const updated = await apiRequest<Payment>(`payments/${paymentId}/sandbox-complete`, {
        method: "POST",
        body: jsonBody({ outcome }),
      });
      setPayment(updated);
      if (updated.status === "captured" && updated.booking_status === "confirmed") {
        router.push(`/bookings/${updated.booking_id}`);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : workflowCopy.paymentActionError);
    } finally {
      setBusy(false);
    }
  }

  const canChooseOutcome = payment?.provider === "sandbox" && payment.status === "pending";

  return (
    <>
      <Nav />
      <main className="min-h-screen bg-[#F7F5F0] px-4 py-12 text-[#20201F] sm:px-6">
        <section className="mx-auto max-w-xl rounded-3xl border border-[#E8E4DC] bg-white p-6 sm:p-9">
          <Link href={payment ? `/bookings/${payment.booking_id}` : "/dashboard"} className="text-sm font-medium text-[#75404A]">
            {workflowCopy.paymentBack}
          </Link>
          <h1 className="mt-6 text-3xl font-semibold">{workflowCopy.paymentTitle}</h1>
          {error ? <p role="alert" className="mt-5 rounded-xl bg-[#F7F5F0] p-4 text-sm text-red-700">{error}</p> : null}
          {!payment && !error ? <p className="mt-5 text-sm text-[#77736D]" aria-live="polite">{workflowCopy.paymentLoading}</p> : null}
          {payment ? (
            <>
              <dl className="mt-6 grid gap-4 rounded-2xl bg-[#F7F5F0] p-5">
                <div>
                  <dt className="text-xs uppercase tracking-wide text-[#77736D]">{workflowCopy.bookingTotal}</dt>
                  <dd className="mt-1 text-lg font-medium">{formatPrice(payment.amount_minor, payment.currency)}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-[#77736D]">{workflowCopy.paymentStatus}</dt>
                  <dd className="mt-1 text-sm capitalize">{payment.status.replaceAll("_", " ")}</dd>
                </div>
              </dl>
              {payment.provider === "sandbox" ? (
                <div className="mt-6 rounded-2xl border border-[#E8E4DC] p-5">
                  <p className="text-sm font-semibold text-[#75404A]">{payment.provider_label}</p>
                  <p className="mt-2 text-sm leading-6 text-[#77736D]">{workflowCopy.paymentSandboxDescription}</p>
                  {canChooseOutcome ? (
                    <div className="mt-5 flex flex-wrap gap-3">
                      <button type="button" disabled={busy} onClick={() => void complete("success")} className="h-11 rounded-full bg-[#75404A] px-5 text-sm font-medium text-white disabled:opacity-50">{workflowCopy.paymentSuccess}</button>
                      <button type="button" disabled={busy} onClick={() => void complete("failure")} className="h-11 rounded-full border border-[#E8E4DC] px-5 text-sm disabled:opacity-50">{workflowCopy.paymentFailure}</button>
                      <button type="button" disabled={busy} onClick={() => void complete("expiry")} className="h-11 rounded-full border border-[#E8E4DC] px-5 text-sm disabled:opacity-50">{workflowCopy.paymentExpiry}</button>
                    </div>
                  ) : (
                    <p className="mt-4 text-sm text-[#77736D]">{workflowCopy.paymentAlreadyComplete}</p>
                  )}
                </div>
              ) : null}
              <Link href={`/bookings/${payment.booking_id}`} className="mt-6 inline-flex rounded-full border border-[#E8E4DC] px-5 py-3 text-sm font-medium">
                {workflowCopy.paymentContinue}
              </Link>
            </>
          ) : null}
        </section>
      </main>
    </>
  );
}
