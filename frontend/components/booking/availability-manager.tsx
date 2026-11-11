"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { Nav } from "@/components/layout/nav";
import { ApiError, apiRequest, jsonBody } from "@/lib/api-client";
import { siteConfig } from "@/lib/site-config";
import { workflowCopy } from "@/lib/workflow-copy";

type Rule = {
  id: string;
  weekday: number;
  start_time: string;
  end_time: string;
  timezone: string;
  is_active: boolean;
};
type AvailabilityException = {
  id: string;
  start_at: string;
  end_at: string;
  exception_type: "available" | "unavailable";
  notes: string;
};
type AvailabilityData = {
  preferences: { minimum_notice_hours: number; max_advance_days: number; buffer_minutes: number };
  rules: Rule[];
  exceptions: AvailabilityException[];
};
const weekDays = workflowCopy.availabilityWeekdays;

function localDateTimeToIso(value: string, timeZone: string) {
  const [year, month, day, hour, minute] = value.split(/[-T:]/).map(Number);
  if ([year, month, day, hour, minute].some((part) => !Number.isInteger(part))) {
    throw new Error(workflowCopy.availabilityInvalidDate);
  }
  const wallTime = Date.UTC(year, month - 1, day, hour, minute);
  let timestamp = wallTime;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const parts = new Intl.DateTimeFormat("en", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).formatToParts(new Date(timestamp));
    const values = Object.fromEntries(parts.map((part) => [part.type, Number(part.value)]));
    const representedWallTime = Date.UTC(
      values.year,
      values.month - 1,
      values.day,
      values.hour,
      values.minute,
    );
    timestamp = wallTime - (representedWallTime - timestamp);
  }
  const resolved = new Date(timestamp);
  const check = new Intl.DateTimeFormat("sv-SE", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(resolved).replace(" ", "T");
  if (check !== value) {
    throw new Error(workflowCopy.availabilityInvalidDate);
  }
  return resolved.toISOString();
}

export function AvailabilityManager() {
  const [data, setData] = useState<AvailabilityData | null>(null);
  const [preferences, setPreferences] = useState<AvailabilityData["preferences"]>({
    minimum_notice_hours: 2,
    max_advance_days: 90,
    buffer_minutes: 0,
  });
  const [weekday, setWeekday] = useState(1);
  const [startTime, setStartTime] = useState("09:00");
  const [endTime, setEndTime] = useState("17:00");
  const [exceptionStart, setExceptionStart] = useState("");
  const [exceptionEnd, setExceptionEnd] = useState("");
  const [exceptionType, setExceptionType] = useState<"available" | "unavailable">("unavailable");
  const [exceptionNotes, setExceptionNotes] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const current = await apiRequest<AvailabilityData>("companions/me/availability");
      setData(current);
      setPreferences(current.preferences);
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiError && reason.status === 403
        ? workflowCopy.availabilitySignIn
        : reason instanceof Error ? reason.message : workflowCopy.availabilityLoadError);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function savePreferences(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const updated = await apiRequest<AvailabilityData["preferences"]>(
        "companions/me/availability/preferences",
        { method: "PATCH", body: jsonBody(preferences) },
      );
      setPreferences(updated);
      setNotice(workflowCopy.availabilitySaved);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : workflowCopy.availabilitySaveError);
    } finally {
      setBusy(false);
    }
  }

  async function addRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await apiRequest("companions/me/availability/rules", {
        method: "POST",
        body: jsonBody({
          weekday,
          start_time: startTime,
          end_time: endTime,
          timezone: siteConfig.timezone,
          is_active: true,
        }),
      });
      await load();
      setNotice(workflowCopy.availabilityRuleAdded);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : workflowCopy.availabilitySaveError);
    } finally {
      setBusy(false);
    }
  }

  async function deleteRule(ruleId: string) {
    setBusy(true);
    setError("");
    try {
      await apiRequest(`companions/me/availability/rules/${ruleId}`, { method: "DELETE" });
      await load();
      setNotice(workflowCopy.availabilityRuleRemoved);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : workflowCopy.availabilitySaveError);
    } finally {
      setBusy(false);
    }
  }

  async function addException(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await apiRequest("companions/me/availability/exceptions", {
        method: "POST",
        body: jsonBody({
          start_at: localDateTimeToIso(exceptionStart, siteConfig.timezone),
          end_at: localDateTimeToIso(exceptionEnd, siteConfig.timezone),
          exception_type: exceptionType,
          notes: exceptionNotes,
        }),
      });
      await load();
      setExceptionNotes("");
      setNotice(workflowCopy.availabilityExceptionAdded);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : workflowCopy.availabilitySaveError);
    } finally {
      setBusy(false);
    }
  }

  async function deleteException(exceptionId: string) {
    setBusy(true);
    setError("");
    try {
      await apiRequest(`companions/me/availability/exceptions/${exceptionId}`, { method: "DELETE" });
      await load();
      setNotice(workflowCopy.availabilityExceptionRemoved);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : workflowCopy.availabilitySaveError);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Nav />
      <main className="min-h-screen bg-[#F7F5F0] px-4 py-12 text-[#20201F] sm:px-6">
        <div className="mx-auto max-w-4xl">
          <Link href="/dashboard/companion" className="text-sm font-medium text-[#75404A]">{workflowCopy.availabilityBack}</Link>
          <h1 className="mt-4 text-3xl font-semibold">{workflowCopy.availabilityTitle}</h1>
          <p className="mt-2 text-sm text-[#77736D]">{workflowCopy.availabilityIntro} {siteConfig.timezone}</p>
          {error ? <p role="alert" className="mt-5 rounded-xl bg-white p-4 text-sm text-red-700">{error}</p> : null}
          {notice ? <p role="status" className="mt-5 rounded-xl bg-white p-4 text-sm text-[#526044]">{notice}</p> : null}
          {!data && !error ? <p className="mt-5 text-sm text-[#77736D]" aria-live="polite">{workflowCopy.availabilityLoading}</p> : null}
          {data ? (
            <>
              <form onSubmit={(event) => void savePreferences(event)} className="mt-7 rounded-2xl border border-[#E8E4DC] bg-white p-6">
                <h2 className="text-lg font-semibold">{workflowCopy.availabilityPreferences}</h2>
                <div className="mt-4 grid gap-4 sm:grid-cols-3">
                  <label className="text-sm">
                    {workflowCopy.availabilityMinimumNotice}
                    <input type="number" min={0} max={720} className="mt-2 h-11 w-full rounded-xl border border-[#E8E4DC] px-3" value={preferences.minimum_notice_hours} onChange={(event) => setPreferences((current) => ({ ...current, minimum_notice_hours: Number(event.target.value) }))} />
                  </label>
                  <label className="text-sm">
                    {workflowCopy.availabilityAdvanceWindow}
                    <input type="number" min={1} max={365} className="mt-2 h-11 w-full rounded-xl border border-[#E8E4DC] px-3" value={preferences.max_advance_days} onChange={(event) => setPreferences((current) => ({ ...current, max_advance_days: Number(event.target.value) }))} />
                  </label>
                  <label className="text-sm">
                    {workflowCopy.availabilityBuffer}
                    <input type="number" min={0} max={1440} className="mt-2 h-11 w-full rounded-xl border border-[#E8E4DC] px-3" value={preferences.buffer_minutes} onChange={(event) => setPreferences((current) => ({ ...current, buffer_minutes: Number(event.target.value) }))} />
                  </label>
                </div>
                <button disabled={busy} className="mt-5 h-11 rounded-full bg-[#75404A] px-5 text-sm font-medium text-white disabled:opacity-50">{workflowCopy.availabilitySave}</button>
              </form>

              <section className="mt-7 rounded-2xl border border-[#E8E4DC] bg-white p-6">
                <h2 className="text-lg font-semibold">{workflowCopy.availabilityWeeklyRules}</h2>
                {data.rules.length ? (
                  <ul className="mt-4 space-y-2">
                    {data.rules.map((rule) => (
                      <li key={rule.id} className="flex flex-wrap items-center justify-between gap-3 border-t border-[#E8E4DC] py-3 text-sm">
                        <span>{weekDays[rule.weekday] ?? workflowCopy.availabilityUnknownDay} · {rule.start_time.slice(0, 5)}–{rule.end_time.slice(0, 5)} · {rule.timezone}</span>
                        <button type="button" disabled={busy} onClick={() => void deleteRule(rule.id)} className="text-[#75404A] disabled:opacity-50">{workflowCopy.availabilityRemove}</button>
                      </li>
                    ))}
                  </ul>
                ) : <p className="mt-3 text-sm text-[#77736D]">{workflowCopy.availabilityNoRules}</p>}
                <form onSubmit={(event) => void addRule(event)} className="mt-5 grid gap-3 border-t border-[#E8E4DC] pt-5 sm:grid-cols-[1.2fr_1fr_1fr_auto]">
                  <label className="text-sm">
                    {workflowCopy.availabilityWeekday}
                    <select className="mt-2 h-11 w-full rounded-xl border border-[#E8E4DC] px-3" value={weekday} onChange={(event) => setWeekday(Number(event.target.value))}>
                      {weekDays.map((day, index) => <option key={day} value={index}>{day}</option>)}
                    </select>
                  </label>
                  <label className="text-sm">
                    {workflowCopy.availabilityStarts}
                    <input required type="time" className="mt-2 h-11 w-full rounded-xl border border-[#E8E4DC] px-3" value={startTime} onChange={(event) => setStartTime(event.target.value)} />
                  </label>
                  <label className="text-sm">
                    {workflowCopy.availabilityEnds}
                    <input required type="time" className="mt-2 h-11 w-full rounded-xl border border-[#E8E4DC] px-3" value={endTime} onChange={(event) => setEndTime(event.target.value)} />
                  </label>
                  <button disabled={busy} className="mt-6 h-11 rounded-full border border-[#E8E4DC] px-4 text-sm disabled:opacity-50">{workflowCopy.availabilityAddRule}</button>
                </form>
              </section>

              <section className="mt-7 rounded-2xl border border-[#E8E4DC] bg-white p-6">
                <h2 className="text-lg font-semibold">{workflowCopy.availabilityExceptions}</h2>
                {data.exceptions.length ? (
                  <ul className="mt-4 space-y-2">
                    {data.exceptions.map((exception) => (
                      <li key={exception.id} className="flex flex-wrap items-center justify-between gap-3 border-t border-[#E8E4DC] py-3 text-sm">
                        <span>
                          <span className="capitalize">{exception.exception_type}</span> · {new Date(exception.start_at).toLocaleString()}–{new Date(exception.end_at).toLocaleTimeString()}
                          {exception.notes ? ` · ${exception.notes}` : ""}
                        </span>
                        <button type="button" disabled={busy} onClick={() => void deleteException(exception.id)} className="text-[#75404A] disabled:opacity-50">{workflowCopy.availabilityRemove}</button>
                      </li>
                    ))}
                  </ul>
                ) : <p className="mt-3 text-sm text-[#77736D]">{workflowCopy.availabilityNoExceptions}</p>}
                <form onSubmit={(event) => void addException(event)} className="mt-5 grid gap-3 border-t border-[#E8E4DC] pt-5 sm:grid-cols-2">
                  <label className="text-sm">
                    {workflowCopy.availabilityExceptionType}
                    <select className="mt-2 h-11 w-full rounded-xl border border-[#E8E4DC] px-3" value={exceptionType} onChange={(event) => setExceptionType(event.target.value as "available" | "unavailable")}>
                      <option value="unavailable">{workflowCopy.availabilityUnavailable}</option>
                      <option value="available">{workflowCopy.availabilityExtraTime}</option>
                    </select>
                  </label>
                  <label className="text-sm">
                    {workflowCopy.availabilityExceptionNotes}
                    <input maxLength={250} className="mt-2 h-11 w-full rounded-xl border border-[#E8E4DC] px-3" value={exceptionNotes} onChange={(event) => setExceptionNotes(event.target.value)} />
                  </label>
                  <label className="text-sm">
                    {workflowCopy.availabilityStarts}
                    <input required type="datetime-local" className="mt-2 h-11 w-full rounded-xl border border-[#E8E4DC] px-3" value={exceptionStart} onChange={(event) => setExceptionStart(event.target.value)} />
                  </label>
                  <label className="text-sm">
                    {workflowCopy.availabilityEnds}
                    <input required type="datetime-local" className="mt-2 h-11 w-full rounded-xl border border-[#E8E4DC] px-3" value={exceptionEnd} onChange={(event) => setExceptionEnd(event.target.value)} />
                  </label>
                  <button disabled={busy} className="h-11 w-fit rounded-full border border-[#E8E4DC] px-5 text-sm disabled:opacity-50">{workflowCopy.availabilityAddException}</button>
                </form>
              </section>
            </>
          ) : null}
        </div>
      </main>
    </>
  );
}
