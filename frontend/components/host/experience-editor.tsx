"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Nav } from "@/components/layout/nav";
import { ApiError, apiRequest, jsonBody } from "@/lib/api-client";
import { currencyMinorUnitScale, fromMinorUnits, toMinorUnits } from "@/lib/currency";
import { siteConfig } from "@/lib/site-config";
import { workflowCopy } from "@/lib/workflow-copy";

type Category = { id: string; slug: string; name: string };
type Experience = {
  id: string;
  title: string;
  summary: string;
  description: string;
  duration_minutes: number;
  min_duration_minutes: number | null;
  max_duration_minutes: number | null;
  pricing_type: "fixed" | "hourly";
  price_minor: number;
  instant_booking_enabled: boolean;
  category_ids: string[];
  image: string;
  status: string;
};
type ExperienceFormValues = Omit<Experience, "id" | "status" | "price_minor"> & { price: number };

const fieldClass =
  "mt-2 h-12 w-full rounded-xl border border-[#E8E4DC] bg-white px-4 font-normal outline-none focus:border-[#75404A]";
const areaClass =
  "mt-2 w-full rounded-xl border border-[#E8E4DC] bg-white px-4 py-3 font-normal outline-none focus:border-[#75404A]";
const emptyExperience: ExperienceFormValues = {
  title: "",
  summary: "",
  description: "",
  duration_minutes: 60,
  min_duration_minutes: null,
  max_duration_minutes: null,
  pricing_type: "fixed",
  price: 0,
  instant_booking_enabled: false,
  category_ids: [],
  image: "/placeholder-experience.svg",
};

type Props = { mode: "create" | "edit"; experienceId?: string };

export function ExperienceEditor({ mode, experienceId }: Props) {
  const router = useRouter();
  const [values, setValues] = useState(emptyExperience);
  const [categories, setCategories] = useState<Category[]>([]);
  const [hostApproved, setHostApproved] = useState(false);
  const [loading, setLoading] = useState(mode === "edit");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      apiRequest<Category[]>("categories"),
      apiRequest<{ status: string }>("companions/me"),
      mode === "edit"
        ? apiRequest<Experience[]>("experiences/manage")
        : Promise.resolve([] as Experience[]),
    ])
      .then(([categoryData, host, experiences]) => {
        if (!active) return;
        setCategories(categoryData);
        setHostApproved(host.status === "approved");
        if (mode === "edit") {
          const current = experiences.find((item) => item.id === experienceId);
          if (!current) {
            setError("Experience not found or you do not have permission to edit it.");
          } else {
            setValues({
              title: current.title,
              summary: current.summary,
              description: current.description,
              duration_minutes: current.duration_minutes,
              min_duration_minutes: current.min_duration_minutes,
              max_duration_minutes: current.max_duration_minutes,
              pricing_type: current.pricing_type,
              price: fromMinorUnits(current.price_minor, siteConfig.currency),
              instant_booking_enabled: current.instant_booking_enabled,
              category_ids: current.category_ids,
              image: current.image,
            });
          }
        }
      })
      .catch((reason: unknown) => setError(
        reason instanceof ApiError && reason.status === 403
          ? "Sign in to manage experiences."
          : reason instanceof Error ? reason.message : "Could not load experience data.",
      ))
      .finally(() => setLoading(false));
    return () => { active = false; };
  }, [experienceId, mode]);

  function update<K extends keyof ExperienceFormValues>(key: K, value: ExperienceFormValues[K]) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  function payload(submitForReview: boolean) {
    const { price, ...experienceValues } = values;
    return {
      ...experienceValues,
      price_minor: toMinorUnits(price, siteConfig.currency),
      duration_minutes: Number(values.duration_minutes),
      min_duration_minutes: values.min_duration_minutes ? Number(values.min_duration_minutes) : null,
      max_duration_minutes: values.max_duration_minutes ? Number(values.max_duration_minutes) : null,
      submit_for_review: submitForReview,
    };
  }

  async function save(submitForReview: boolean) {
    setError("");
    setNotice("");
    if (submitForReview && !hostApproved) {
      setError("Host approval is required before publishing an experience.");
      return;
    }
    setBusy(true);
    try {
      const saved = await apiRequest<Experience>(
        mode === "create" ? "experiences/manage" : `experiences/manage/${experienceId}`,
        {
          method: mode === "create" ? "POST" : "PATCH",
          body: jsonBody(payload(submitForReview)),
        },
      );
      if (mode === "create") {
        router.replace(`/dashboard/companion/experiences/${saved.id}/edit`);
      } else {
        setNotice(
          saved.status === "pending_review"
            ? "Submitted to the moderation queue. It will appear publicly after review."
            : submitForReview
              ? "Your experience is now published."
              : "Draft saved.",
        );
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save this experience.");
    } finally {
      setBusy(false);
    }
  }

  async function deactivate() {
    if (!experienceId) return;
    setBusy(true);
    setError("");
    try {
      await apiRequest<void>(`experiences/manage/${experienceId}`, { method: "DELETE" });
      setNotice("Experience deactivated.");
      router.push("/dashboard/companion");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not deactivate this experience.");
      setBusy(false);
    }
  }

  return (
    <>
      <Nav />
      <main className="min-h-screen bg-[#F7F5F0] px-4 py-12 text-[#20201F] sm:px-6">
        <section className="mx-auto max-w-3xl rounded-3xl border border-[#E8E4DC] bg-white p-6 sm:p-9">
          <Link href="/dashboard/companion" className="text-sm font-medium text-[#75404A]">← Host dashboard</Link>
          <h1 className="mt-7 text-3xl font-semibold">{mode === "create" ? "Create an experience" : "Edit experience"}</h1>
          <p className="mt-2 text-sm leading-6 text-[#77736D]">
            {workflowCopy.experienceFormDescription}
          </p>
          {loading ? <p className="mt-7 text-sm text-[#77736D]">Loading experience…</p> : (
            <form className="mt-7 space-y-5" onSubmit={(event) => {
              event.preventDefault();
              void save(false);
            }}>
              <label className="block text-sm font-medium">
                Title
                <input required maxLength={180} className={fieldClass} value={values.title} onChange={(event) => update("title", event.target.value)} />
              </label>
              <label className="block text-sm font-medium">
                Short summary
                <input maxLength={300} className={fieldClass} value={values.summary} onChange={(event) => update("summary", event.target.value)} />
              </label>
              <label className="block text-sm font-medium">
                Description
                <textarea required rows={6} className={areaClass} value={values.description} onChange={(event) => update("description", event.target.value)} />
              </label>
              <div className="grid gap-5 sm:grid-cols-2">
                <label className="block text-sm font-medium">
                  Duration in minutes
                  <input type="number" min={15} max={1440} required className={fieldClass} value={values.duration_minutes} onChange={(event) => update("duration_minutes", Number(event.target.value))} />
                </label>
                <label className="block text-sm font-medium">
                  {workflowCopy.experiencePriceLabel(siteConfig.currency)}
                  <input type="number" min={0} step={1 / currencyMinorUnitScale(siteConfig.currency)} required className={fieldClass} value={values.price} onChange={(event) => update("price", Number(event.target.value))} />
                </label>
                <label className="block text-sm font-medium">
                  Minimum duration (optional)
                  <input type="number" min={15} max={1440} className={fieldClass} value={values.min_duration_minutes ?? ""} onChange={(event) => update("min_duration_minutes", event.target.value ? Number(event.target.value) : null)} />
                </label>
                <label className="block text-sm font-medium">
                  Maximum duration (optional)
                  <input type="number" min={15} max={1440} className={fieldClass} value={values.max_duration_minutes ?? ""} onChange={(event) => update("max_duration_minutes", event.target.value ? Number(event.target.value) : null)} />
                </label>
              </div>
              <label className="block text-sm font-medium">
                Pricing type
                <select className={fieldClass} value={values.pricing_type} onChange={(event) => update("pricing_type", event.target.value as "fixed" | "hourly")}>
                  <option value="fixed">Fixed</option>
                  <option value="hourly">Hourly</option>
                </select>
              </label>
              <fieldset>
                <legend className="text-sm font-medium">Categories</legend>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {categories.map((category) => (
                    <label key={category.id} className="flex items-center gap-2 rounded-xl border border-[#E8E4DC] px-3 py-2.5 text-sm">
                      <input
                        type="checkbox"
                        checked={values.category_ids.includes(category.id)}
                        onChange={(event) => update(
                          "category_ids",
                          event.target.checked
                            ? [...values.category_ids, category.id]
                            : values.category_ids.filter((id) => id !== category.id),
                        )}
                        className="accent-[#75404A]"
                      />
                      {category.name}
                    </label>
                  ))}
                </div>
              </fieldset>
              <label className="block text-sm font-medium">
                Experience photo URL
                <input className={fieldClass} value={values.image} onChange={(event) => update("image", event.target.value)} placeholder="/placeholder-experience.svg" />
                <span className="mt-1 block text-xs font-normal text-[#77736D]">Use a local path or HTTPS URL. Never upload identity documents.</span>
              </label>
              <label className="flex items-center gap-3 text-sm">
                <input type="checkbox" checked={values.instant_booking_enabled} onChange={(event) => update("instant_booking_enabled", event.target.checked)} className="accent-[#75404A]" />
                Allow instant booking
              </label>
              {!hostApproved ? (
                <p className="rounded-xl bg-[#F7F5F0] p-4 text-sm leading-6 text-[#77736D]">
                  Save a draft now; publishing becomes available after host approval.{" "}
                  <Link href="/become-a-companion" className="font-medium text-[#75404A]">Complete onboarding</Link>
                </p>
              ) : null}
              {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
              {notice ? <p role="status" className="text-sm text-[#526044]">{notice}</p> : null}
              <div className="flex flex-wrap gap-3 pt-2">
                <button type="submit" disabled={busy} className="h-12 rounded-full border border-[#E8E4DC] px-5 text-sm font-medium disabled:opacity-60">
                  {busy ? "Saving…" : "Save draft"}
                </button>
                <button type="button" disabled={busy || !hostApproved} onClick={(event) => {
                  const form = event.currentTarget.form;
                  if (form?.reportValidity()) {
                    void save(true);
                  }
                }} className="h-12 rounded-full bg-[#75404A] px-5 text-sm font-medium text-white disabled:opacity-50">
                  Submit for publishing
                </button>
                {mode === "edit" ? (
                  <button type="button" disabled={busy} onClick={() => void deactivate()} className="h-12 rounded-full px-4 text-sm font-medium text-red-700 disabled:opacity-50">
                    Deactivate
                  </button>
                ) : null}
              </div>
            </form>
          )}
        </section>
      </main>
    </>
  );
}
