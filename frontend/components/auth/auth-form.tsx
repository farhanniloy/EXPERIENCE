"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { apiRequest, jsonBody } from "@/lib/api-client";
import { workflowCopy } from "@/lib/workflow-copy";

type Props = { mode: "login" | "register" };
type Account = { id: string; email: string; display_name: string };

export function AuthForm({ mode }: Props) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    const values = new FormData(event.currentTarget);
    const payload = {
      email: String(values.get("email") ?? ""),
      password: String(values.get("password") ?? ""),
      ...(mode === "register"
        ? { display_name: String(values.get("display_name") ?? "") }
        : {}),
    };

    try {
      if (mode === "register") {
        await apiRequest<Account>("auth/register", {
          method: "POST",
          body: jsonBody(payload),
        });
      }
      await apiRequest<Account>("auth/login", {
        method: "POST",
        body: jsonBody({ email: payload.email, password: payload.password }),
      });
      router.push("/dashboard");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to continue. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#F7F5F0] px-4 py-16 text-[#20201F]">
      <section className="mx-auto max-w-md rounded-3xl border border-[#E8E4DC] bg-white p-7 sm:p-9">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">Along</p>
        <h1 className="mt-4 text-3xl font-semibold">
          {mode === "login" ? workflowCopy.signInTitle : workflowCopy.signUpTitle}
        </h1>
        <p className="mt-3 text-sm leading-6 text-[#77736D]">{workflowCopy.authDescription}</p>
        <form className="mt-8 space-y-5" onSubmit={submit}>
          {mode === "register" ? (
            <label className="block text-sm font-medium">
              {workflowCopy.displayNameLabel}
              <input
                name="display_name"
                required
                maxLength={120}
                autoComplete="name"
                className="mt-2 h-12 w-full rounded-xl border border-[#E8E4DC] px-4 font-normal outline-none focus:border-[#75404A]"
              />
            </label>
          ) : null}
          <label className="block text-sm font-medium">
            {workflowCopy.emailLabel}
            <input
              name="email"
              type="email"
              required
              autoComplete="email"
              className="mt-2 h-12 w-full rounded-xl border border-[#E8E4DC] px-4 font-normal outline-none focus:border-[#75404A]"
            />
          </label>
          <label className="block text-sm font-medium">
            {workflowCopy.passwordLabel}
            <input
              name="password"
              type="password"
              required
              minLength={8}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              className="mt-2 h-12 w-full rounded-xl border border-[#E8E4DC] px-4 font-normal outline-none focus:border-[#75404A]"
            />
          </label>
          {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
          <button
            type="submit"
            disabled={busy}
            className="h-12 w-full rounded-full bg-[#75404A] px-5 text-sm font-medium text-white transition hover:bg-[#62373d] disabled:opacity-60"
          >
            {busy ? "Please wait…" : mode === "login" ? workflowCopy.signInAction : workflowCopy.signUpAction}
          </button>
        </form>
        <p className="mt-6 text-center text-sm text-[#77736D]">
          {mode === "login" ? "New to Along?" : "Already have an account?"}{" "}
          <Link className="font-medium text-[#75404A]" href={mode === "login" ? "/signup" : "/login"}>
            {mode === "login" ? "Create an account" : "Sign in"}
          </Link>
        </p>
      </section>
    </main>
  );
}
