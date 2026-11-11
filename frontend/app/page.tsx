"use client";

import { useEffect, useState } from "react";

type HealthResponse = {
  status: string;
  service: string;
  environment: string;
  timezone: string;
};

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/v1/health/")
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Health check failed with ${response.status}`);
        }

        const data = (await response.json()) as HealthResponse;
        setHealth(data);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "The backend health check is failing.");
      });
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#F7F5F0] px-6 py-16 text-[#20201F]">
      <div className="w-full max-w-2xl rounded-2xl border border-[#E8E4DC] bg-white p-8 shadow-sm">
        <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">
          Along foundation
        </p>
        <h1 className="text-3xl font-semibold tracking-tight">Marketplace foundation ready</h1>
        <p className="mt-3 text-base text-[#77736D]">
          This frontend calls the Django API through the local same-origin proxy and confirms the
          service is healthy.
        </p>

        <div className="mt-8 rounded-xl bg-[#F7F5F0] p-5">
          {error ? (
            <p className="text-sm text-red-700">{error}</p>
          ) : health ? (
            <div className="space-y-2 text-sm text-[#20201F]">
              <p>
                <span className="font-medium">Status:</span> {health.status}
              </p>
              <p>
                <span className="font-medium">Service:</span> {health.service}
              </p>
              <p>
                <span className="font-medium">Environment:</span> {health.environment}
              </p>
              <p>
                <span className="font-medium">Timezone:</span> {health.timezone}
              </p>
            </div>
          ) : (
            <p className="text-sm text-[#77736D]">Checking the backend health endpoint…</p>
          )}
        </div>
      </div>
    </main>
  );
}
