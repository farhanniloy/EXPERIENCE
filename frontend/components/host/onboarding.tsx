"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { ApiError, apiRequest, jsonBody } from "@/lib/api-client";
import { workflowCopy } from "@/lib/workflow-copy";

type HostProfile = {
  display_name: string;
  headline: string;
  biography: string;
  city: string;
  languages: string[];
  interests: string[];
  photos: string[];
  status: string;
  adult_confirmed: boolean;
  verification_provider: string | null;
};

type Step = "age" | "profile" | "photos" | "submit";
const steps: Step[] = ["age", "profile", "photos", "submit"];
const inputClass =
  "mt-2 h-12 w-full rounded-xl border border-[#E8E4DC] bg-white px-4 font-normal outline-none focus:border-[#75404A]";
const textAreaClass =
  "mt-2 w-full rounded-xl border border-[#E8E4DC] bg-white px-4 py-3 font-normal outline-none focus:border-[#75404A]";

function splitList(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

export function HostOnboarding() {
  const [profile, setProfile] = useState<HostProfile | null>(null);
  const [step, setStep] = useState<Step>("age");
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [headline, setHeadline] = useState("");
  const [biography, setBiography] = useState("");
  const [city, setCity] = useState("");
  const [languages, setLanguages] = useState("");
  const [interests, setInterests] = useState("");
  const [photos, setPhotos] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [needsLogin, setNeedsLogin] = useState(false);

  useEffect(() => {
    apiRequest<HostProfile>("companions/me")
      .then((data) => {
        setProfile(data);
        setDisplayName(data.display_name);
        setHeadline(data.headline);
        setBiography(data.biography);
        setCity(data.city);
        setLanguages(data.languages.join(", "));
        setInterests(data.interests.join(", "));
        setPhotos(data.photos.join("\n"));
        setStep(data.adult_confirmed ? "profile" : "age");
      })
      .catch((reason: unknown) => {
        setNeedsLogin(reason instanceof ApiError && (reason.status === 401 || reason.status === 403));
        setError(reason instanceof ApiError && reason.status === 403
          ? "Sign in to begin host onboarding."
          : reason instanceof Error ? reason.message : "Could not load your profile.");
      })
      .finally(() => setLoading(false));
  }, []);

  const currentIndex = steps.indexOf(step);

  async function saveProfile() {
    return apiRequest<HostProfile>("companions/me", {
      method: "PATCH",
      body: jsonBody({
        display_name: displayName,
        headline,
        biography,
        city,
        languages: splitList(languages),
        interests: splitList(interests),
        photos: photos.split("\n").map((item) => item.trim()).filter(Boolean),
      }),
    });
  }

  async function continueStep(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    try {
      if (step === "age") {
        const result = await apiRequest<{ label: string }>("companions/me/verification", {
          method: "POST",
          body: jsonBody({ confirmed_18: ageConfirmed }),
        });
        setNotice(result.label);
        setStep("profile");
      } else if (step === "profile") {
        const saved = await saveProfile();
        setProfile(saved);
        setNotice("Draft saved.");
        setStep("photos");
      } else if (step === "photos") {
        const saved = await saveProfile();
        setProfile(saved);
        setNotice("Draft saved.");
        setStep("submit");
      } else {
        await saveProfile();
        const submitted = await apiRequest<HostProfile>("companions/applications", {
          method: "POST",
          body: jsonBody({
            display_name: displayName,
            headline,
            biography,
            city,
            languages: splitList(languages),
            interests: splitList(interests),
            photos: photos.split("\n").map((item) => item.trim()).filter(Boolean),
          }),
        });
        setProfile(submitted);
        setNotice("Your application is in the review queue.");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save your application.");
    } finally {
      setBusy(false);
    }
  }

  async function saveDraft() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const saved = await saveProfile();
      setProfile(saved);
      setNotice("Draft saved.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save your draft.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <p className="py-16 text-center text-sm text-[#77736D]">Loading your host profile…</p>;
  }

  const submitted = profile?.status === "submitted" || profile?.status === "under_review";

  return (
    <main className="min-h-screen bg-[#F7F5F0] px-4 py-12 text-[#20201F] sm:px-6">
      <section className="mx-auto max-w-3xl rounded-3xl border border-[#E8E4DC] bg-white p-6 sm:p-10">
        <Link href="/" className="text-sm font-medium text-[#75404A]">← Along</Link>
        <p className="mt-8 text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">Host onboarding</p>
        <h1 className="mt-3 text-3xl font-semibold">{workflowCopy.onboardingTitle}</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-[#77736D]">{workflowCopy.onboardingIntro}</p>

        <ol className="mt-8 grid grid-cols-4 gap-2" aria-label="Onboarding progress">
          {steps.map((item, index) => (
            <li key={item} className={`h-1.5 rounded-full ${index <= currentIndex ? "bg-[#75404A]" : "bg-[#E8E4DC]"}`} />
          ))}
        </ol>

        {submitted ? (
          <div className="mt-8 rounded-2xl border border-[#E8E4DC] bg-[#F7F5F0] p-6">
            <h2 className="text-xl font-semibold">Application under review</h2>
            <p className="mt-2 text-sm leading-6 text-[#77736D]">
              Your host profile has been submitted. You can check back on the host dashboard after review.
            </p>
            <Link href="/dashboard/companion" className="mt-5 inline-flex rounded-full bg-[#75404A] px-5 py-3 text-sm font-medium text-white">
              Go to host dashboard
            </Link>
          </div>
        ) : (
          <form onSubmit={continueStep} className="mt-8 space-y-6">
            {step === "age" ? (
              <section>
                <h2 className="text-xl font-semibold">{workflowCopy.ageStepTitle}</h2>
                <p className="mt-2 text-sm leading-6 text-[#77736D]">{workflowCopy.ageStepWarning}</p>
                <label className="mt-5 flex items-start gap-3 text-sm leading-6">
                  <input
                    type="checkbox"
                    required
                    checked={ageConfirmed}
                    onChange={(event) => setAgeConfirmed(event.target.checked)}
                    className="mt-1 accent-[#75404A]"
                  />
                  {workflowCopy.ageConfirmLabel}
                </label>
                <p className="mt-4 rounded-xl bg-[#F7F5F0] p-4 text-xs leading-5 text-[#77736D]">
                  {workflowCopy.developmentAdapter}: this local adapter only records your self-confirmation. It does not check identity or documents.
                </p>
              </section>
            ) : null}

            {step === "profile" ? (
              <section className="space-y-5">
                <h2 className="text-xl font-semibold">{workflowCopy.profileStepTitle}</h2>
                <label className="block text-sm font-medium">
                  Display name
                  <input className={inputClass} required maxLength={120} value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
                </label>
                <label className="block text-sm font-medium">
                  Headline
                  <input className={inputClass} required maxLength={180} value={headline} onChange={(event) => setHeadline(event.target.value)} />
                </label>
                <label className="block text-sm font-medium">
                  About you
                  <textarea className={textAreaClass} rows={5} value={biography} onChange={(event) => setBiography(event.target.value)} />
                </label>
                <label className="block text-sm font-medium">
                  Service city
                  <input className={inputClass} required maxLength={100} value={city} onChange={(event) => setCity(event.target.value)} />
                </label>
                <label className="block text-sm font-medium">
                  Languages
                  <input className={inputClass} required value={languages} onChange={(event) => setLanguages(event.target.value)} placeholder="English, Bangla" />
                </label>
                <label className="block text-sm font-medium">
                  Interests
                  <input className={inputClass} required value={interests} onChange={(event) => setInterests(event.target.value)} placeholder="Museums, cafés, photography" />
                </label>
              </section>
            ) : null}

            {step === "photos" ? (
              <section>
                <h2 className="text-xl font-semibold">Profile photos</h2>
                <p className="mt-2 text-sm leading-6 text-[#77736D]">{workflowCopy.photosHelp}</p>
                <textarea className={`${textAreaClass} mt-5`} rows={5} value={photos} onChange={(event) => setPhotos(event.target.value)} placeholder="/placeholder-host.svg" />
                <p className="mt-2 text-xs text-[#77736D]">Photos are public profile images. Do not include identity documents or private contact details.</p>
              </section>
            ) : null}

            {step === "submit" ? (
              <section>
                <h2 className="text-xl font-semibold">Review and submit</h2>
                <p className="mt-2 text-sm leading-6 text-[#77736D]">
                  We’ll check that your profile follows Along’s public-venue, adults-only, non-sexual safety standards.
                </p>
                <div className="mt-5 rounded-2xl bg-[#F7F5F0] p-5 text-sm">
                  <p className="font-medium">{displayName} · {city}</p>
                  <p className="mt-1 text-[#77736D]">{headline}</p>
                  <p className="mt-3 text-[#77736D]">{languages} · {interests}</p>
                  {profile?.verification_provider ? (
                    <p className="mt-3 text-xs text-[#77736D]">
                      Age confirmation provider: {profile.verification_provider} (development simulation)
                    </p>
                  ) : null}
                </div>
              </section>
            ) : null}

            {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
            {needsLogin ? <Link href="/login" className="inline-flex text-sm font-medium text-[#75404A]">Sign in to continue</Link> : null}
            {notice ? <p role="status" className="text-sm text-[#526044]">{notice}</p> : null}
            <div className="flex flex-wrap gap-3 pt-2">
              {currentIndex > 0 ? (
                <button type="button" onClick={() => setStep(steps[currentIndex - 1])} className="h-12 rounded-full border border-[#E8E4DC] px-5 text-sm font-medium">
                  Back
                </button>
              ) : null}
              {step !== "submit" ? (
                <button type="submit" disabled={busy} className="h-12 rounded-full bg-[#75404A] px-6 text-sm font-medium text-white disabled:opacity-60">
                  {busy ? "Saving…" : step === "age" ? "Confirm and continue" : workflowCopy.saveDraft}
                </button>
              ) : (
                <button type="submit" disabled={busy} className="h-12 rounded-full bg-[#75404A] px-6 text-sm font-medium text-white disabled:opacity-60">
                  {busy ? "Submitting…" : workflowCopy.submitApplication}
                </button>
              )}
              {step !== "age" ? (
                <button type="button" disabled={busy} onClick={() => void saveDraft()} className="h-12 rounded-full px-4 text-sm font-medium text-[#75404A] disabled:opacity-60">
                  Save draft
                </button>
              ) : null}
            </div>
          </form>
        )}
      </section>
    </main>
  );
}
