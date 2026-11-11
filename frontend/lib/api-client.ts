type CsrfResponse = { csrfToken: string };
type ApiErrorBody = {
  error?: { message?: string };
  detail?: string;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function csrfToken() {
  const response = await fetch("/api/v1/auth/csrf", {
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new ApiError("Could not start a secure session. Please try again.", response.status);
  }
  const body = (await response.json()) as CsrfResponse;
  return body.csrfToken;
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!["GET", "HEAD", "OPTIONS", "TRACE"].includes(method)) {
    headers.set("X-CSRFToken", await csrfToken());
  }

  const response = await fetch(`/api/v1/${path.replace(/^\/+/, "")}`, {
    ...init,
    method,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    throw new ApiError(
      body.error?.message ?? body.detail ?? `Request failed (${response.status}).`,
      response.status,
    );
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function jsonBody(value: unknown) {
  return JSON.stringify(value);
}
