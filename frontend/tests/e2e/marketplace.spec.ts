import { expect, test, type Page, type Route } from "@playwright/test";

type ApiHandler = (route: Route) => Promise<void>;

const csrfToken = "playwright-csrf-token";

function respond(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function mockApi(page: Page, handlers: Record<string, ApiHandler>) {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/^\/api\/v1\//, "");
    if (path === "auth/csrf") {
      await respond(route, { csrfToken });
      return;
    }

    const handler = handlers[`${request.method()} ${path}`];
    if (handler) {
      await handler(route);
      return;
    }
    await respond(route, { detail: `Unexpected API request: ${request.method()} ${path}` }, 404);
  });
}

async function registerAccount(page: Page, displayName = "Test Customer") {
  await page.goto("/signup");
  await page.getByLabel("Display name").fill(displayName);
  await page.getByLabel("Email address").fill(`e2e-${crypto.randomUUID()}@example.test`);
  await page.getByLabel("Password").fill("Along-E2E-Password-391!");
  await page.getByRole("button", { name: "Create account" }).click();
}

function emptyMarketplace() {
  return {
    site: {
      brand: "Along",
      tagline: "Good company. Great experiences.",
      currency: "BDT",
      timezone: "Asia/Dhaka",
      country: "BD",
      city: "Dhaka",
    },
    categories: [],
    experiences: [],
    companions: [],
    collections: [],
  };
}

function emptyPage() {
  return { results: [] };
}

test("customer can register, reach an empty dashboard, and browse the public home page", async ({ page }) => {
  await mockApi(page, {
    "POST auth/register": (route) => respond(route, { id: "customer-id", email: "customer@example.test", display_name: "Test Customer" }, 201),
    "POST auth/login": (route) => respond(route, { id: "customer-id", email: "customer@example.test", display_name: "Test Customer" }),
    "GET dashboard": (route) => respond(route, { display_name: "Test Customer", bookings: [] }),
    "GET public/marketplace": (route) => respond(route, emptyMarketplace()),
    "GET categories": (route) => respond(route, []),
    "GET experiences": (route) => respond(route, emptyPage()),
    "GET companions": (route) => respond(route, emptyPage()),
    "GET collections": (route) => respond(route, emptyPage()),
  });

  await registerAccount(page);
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText("Your bookings will appear here.")).toBeVisible();
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Make plans worth remembering." })).toBeVisible();
  await expect(page.getByRole("link", { name: "Explore experiences" })).toBeVisible();
});

test("host can complete adult confirmation and submit a profile for review", async ({ page }) => {
  const submittedRequests: string[] = [];
  const profile = {
    display_name: "Test Host",
    headline: "",
    biography: "",
    city: "",
    languages: [],
    interests: [],
    photos: [],
    status: "draft",
    adult_confirmed: false,
    verification_provider: null,
  };

  await mockApi(page, {
    "POST auth/register": (route) => respond(route, { id: "host-id", email: "host@example.test", display_name: "Test Host" }, 201),
    "POST auth/login": (route) => respond(route, { id: "host-id", email: "host@example.test", display_name: "Test Host" }),
    "GET companions/me": (route) => respond(route, profile),
    "POST companions/me/verification": async (route) => {
      submittedRequests.push(route.request().headers()["x-csrftoken"] ?? "");
      await respond(route, { label: "Development confirmation recorded." });
    },
    "PATCH companions/me": async (route) => {
      submittedRequests.push(route.request().headers()["x-csrftoken"] ?? "");
      await respond(route, { ...profile, adult_confirmed: true });
    },
    "POST companions/applications": async (route) => {
      submittedRequests.push(route.request().headers()["x-csrftoken"] ?? "");
      await respond(route, { ...profile, status: "submitted", adult_confirmed: true }, 202);
    },
    "GET dashboard/companion": (route) => respond(route, {
      host: { display_name: "Test Host", status: "submitted", adult_confirmed: true, verification_provider: "development_mock" },
      experiences: [],
      bookings: [],
    }),
  });

  await registerAccount(page, "Test Host");
  await page.goto("/become-a-companion");
  await expect(page.getByText("Adults-only confirmation")).toBeVisible();
  await page.getByLabel("I confirm that I am at least 18 years old.").check();
  await page.getByRole("button", { name: "Confirm and continue" }).click();

  await page.getByLabel("Display name").fill("Test Host");
  await page.getByLabel("Headline").fill("A guide to public museums");
  await page.getByLabel("About you").fill("I enjoy local art and museum visits.");
  await page.getByLabel("Service city").fill("Dhaka");
  await page.getByLabel("Languages").fill("English, Bangla");
  await page.getByLabel("Interests").fill("Museums, photography");
  await page.getByRole("button", { name: "Save draft and continue" }).click();
  await page.getByPlaceholder("/placeholder-host.svg").fill("/placeholder-host.svg");
  await page.getByRole("button", { name: "Save draft and continue" }).click();
  await page.getByRole("button", { name: "Submit for review" }).click();

  await expect(page.getByRole("heading", { name: "Application under review" })).toBeVisible();
  expect(submittedRequests).toHaveLength(5);
  expect(submittedRequests.every((header) => header === csrfToken)).toBe(true);
  await page.goto("/dashboard/companion");
  await expect(page.getByRole("heading", { name: "Host dashboard" })).toBeVisible();
  await expect(page.getByText("Your experiences will appear here.")).toBeVisible();
});

test("staff can resolve a report from the administration workspace", async ({ page }) => {
  let reportPending = true;
  let csrfHeader = "";
  const dashboard = () => ({
    counts: {
      bookings: 0,
      payments: 0,
      open_reports: reportPending ? 1 : 0,
      pending_reviews: 0,
      pending_applications: 0,
      active_collections: 0,
    },
    can_suspend_accounts: false,
    bookings: [],
    payments: [],
    reports: reportPending
      ? [{
          id: "safety-report-id",
          reporter: "Customer",
          reported: "Host",
          booking_id: "booking-id",
          experience_title: "Museum visit",
          reason: "safety_concern",
          description: "Please review this report.",
          status: "open",
          created_at: "2026-11-12T00:00:00Z",
          incident_status: "open",
        }]
      : [],
    reviews: [],
    audit_log_count: 1,
  });

  await mockApi(page, {
    "GET admin/dashboard": (route) => respond(route, dashboard()),
    "POST admin/reports/safety-report-id": async (route) => {
      csrfHeader = route.request().headers()["x-csrftoken"] ?? "";
      reportPending = false;
      await respond(route, { status: "resolved" });
    },
  });

  await page.goto("/admin");
  await expect(page.getByText("Please review this report.")).toBeVisible();
  await page.getByRole("button", { name: "Resolve" }).click();
  await expect(page.getByText("No reports yet.")).toBeVisible();
  expect(csrfHeader).toBe(csrfToken);
});

test("admin workspace reports and denies a non-staff session", async ({ page }) => {
  await mockApi(page, {
    "GET admin/dashboard": (route) => respond(route, { detail: "You do not have permission to perform this action." }, 403),
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/admin");
  await expect(page.locator("p[role=alert]")).toContainText("staff administrators only");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test("customer can check in and report a concern from booking details", async ({ page }) => {
  const bookingId = "d129ca8b-984e-4e51-9691-8c4c0dbdd1d0";
  const booking = {
    id: bookingId,
    conversation_id: null,
    other_party_user_id: "d433908c-8682-4564-9aa4-9a7f34a72e15",
    status: "confirmed",
    start_at: "2026-12-01T04:00:00Z",
    end_at: "2026-12-01T05:00:00Z",
    timezone: "Asia/Dhaka",
    experience_title: "Museum visit",
    other_party: "Sample Host",
    viewer_role: "customer",
    public_venue_name: "Bangladesh National Museum",
    customer_note: "",
    total_minor: 120000,
    currency: "BDT",
    payment_deadline: null,
  };
  const cancelledBooking = { ...booking, status: "cancelled" };
  const writes: string[] = [];

  await mockApi(page, {
    [`GET bookings/${bookingId}`]: (route) => respond(route, booking),
    [`GET bookings/${bookingId}/events`]: (route) => respond(route, []),
    [`POST bookings/${bookingId}/check-in`]: async (route) => {
      writes.push("check-in");
      await respond(route, { status: "safe", safety_team_notified: false });
    },
    [`POST bookings/${bookingId}/cancel`]: async (route) => {
      writes.push("cancel");
      await respond(route, cancelledBooking);
    },
    "POST users/d433908c-8682-4564-9aa4-9a7f34a72e15/block": async (route) => {
      writes.push("block");
      await respond(route, { blocked: true }, 201);
    },
    "POST reports": async (route) => {
      writes.push("report");
      await respond(route, { id: "report-id", status: "open" }, 201);
    },
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/bookings/${bookingId}`);
  await expect(page.getByRole("heading", { name: "Booking details" })).toBeVisible();
  await page.getByRole("button", { name: "I'm safe" }).click();
  await expect(page.locator("p[role=status]").filter({ hasText: "Your safety check-in was recorded." })).toBeVisible();
  await page.getByRole("button", { name: "Report a safety concern" }).click();
  await page.getByLabel("What happened?").fill("The meeting place changed unexpectedly.");
  await page.getByRole("button", { name: "Send report" }).click();
  await expect(page.locator("p[role=status]").filter({ hasText: "Your report was sent to the safety team." })).toBeVisible();
  await page.getByRole("button", { name: "Block this account" }).click();
  await expect(page.locator("[role=status]").filter({ hasText: "This account has been blocked." })).toBeVisible();
  await page.getByRole("button", { name: "Cancel booking" }).click();
  await expect(page.getByText("cancelled", { exact: true })).toBeVisible();
  expect(writes).toEqual(["check-in", "report", "block", "cancel"]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test("customer can submit a review only from a completed booking", async ({ page }) => {
  const bookingId = "e6679a4f-547e-4e1f-b91a-9c4a98e6db30";
  const booking = {
    id: bookingId,
    conversation_id: null,
    other_party_user_id: "d433908c-8682-4564-9aa4-9a7f34a72e15",
    status: "completed",
    start_at: "2026-12-01T04:00:00Z",
    end_at: "2026-12-01T05:00:00Z",
    timezone: "Asia/Dhaka",
    experience_title: "Museum visit",
    other_party: "Sample Host",
    viewer_role: "customer",
    public_venue_name: "Bangladesh National Museum",
    customer_note: "",
    total_minor: 120000,
    currency: "BDT",
    payment_deadline: null,
  };
  let reviewBody: Record<string, unknown> = {};

  await mockApi(page, {
    [`GET bookings/${bookingId}`]: (route) => respond(route, booking),
    [`GET bookings/${bookingId}/events`]: (route) => respond(route, []),
    [`POST bookings/${bookingId}/review`]: async (route) => {
      reviewBody = JSON.parse(route.request().postData() ?? "{}") as Record<string, unknown>;
      await respond(route, { id: "review-id", status: "pending", verified_booking: true }, 201);
    },
  });

  await page.goto(`/bookings/${bookingId}`);
  await page.getByLabel("Public review (optional)").fill("A thoughtful museum visit.");
  await page.getByLabel("Private safety feedback (only moderators can see this)").fill("No concerns.");
  await page.getByRole("button", { name: "Submit review" }).click();
  await expect(page.locator("p[role=status]").filter({ hasText: "Your review is awaiting moderation." })).toBeVisible();
  expect(reviewBody["private_safety_feedback"]).toBe("No concerns.");
});

test("booking retry reuses its idempotency key and handles empty slots", async ({ page }) => {
  const experience = {
    id: "26f67693-2ccf-4e90-8c0f-d5cfc20e98c2",
    slug: "e2e-museum-visit",
    title: "Museum visit",
    city: "Dhaka",
    summary: "A public museum visit.",
    description: "Explore a museum together.",
    price_minor: 120000,
    currency: "BDT",
    duration_minutes: 60,
    min_duration_minutes: null,
    max_duration_minutes: null,
    category: "museums",
    rating: 0,
    instant_book: false,
    host_name: "Sample Host",
    host_slug: "sample-host",
    image: "/placeholder-experience.svg",
    tags: [],
  };
  let slotDate = "";
  let offerSlot = false;
  let bookingAttempts = 0;
  const idempotencyKeys: string[] = [];

  await mockApi(page, {
    "GET public/marketplace": (route) => respond(route, { ...emptyMarketplace(), experiences: [experience] }),
    "GET categories": (route) => respond(route, []),
    "GET experiences": (route) => respond(route, emptyPage()),
    "GET companions": (route) => respond(route, emptyPage()),
    "GET collections": (route) => respond(route, emptyPage()),
    "GET experiences/e2e-museum-visit/availability": async (route) => {
      const requestURL = new URL(route.request().url());
      slotDate = requestURL.searchParams.get("from") ?? "";
      const slots = offerSlot
        ? [{ start_at: `${slotDate}T04:00:00Z`, end_at: `${slotDate}T05:00:00Z`, timezone: "Asia/Dhaka" }]
        : [];
      await respond(route, slots);
    },
    "POST companions/me/verification": (route) => respond(route, { label: "Development confirmation recorded." }),
    "POST bookings": async (route) => {
      bookingAttempts += 1;
      idempotencyKeys.push(route.request().headers()["idempotency-key"] ?? "");
      if (bookingAttempts === 1) {
        await respond(route, { detail: "Temporary booking error." }, 503);
        return;
      }
      await respond(route, { id: "8a79a96c-c713-477d-8be3-9783eddf4e88" }, 201);
    },
    "GET bookings/8a79a96c-c713-477d-8be3-9783eddf4e88": (route) => respond(route, {
      id: "8a79a96c-c713-477d-8be3-9783eddf4e88",
      conversation_id: null,
      other_party_user_id: null,
      status: "requested",
      start_at: "2026-12-01T04:00:00Z",
      end_at: "2026-12-01T05:00:00Z",
      timezone: "Asia/Dhaka",
      experience_title: "Museum visit",
      other_party: "Sample Host",
      viewer_role: "customer",
      public_venue_name: "Bangladesh National Museum",
      customer_note: "",
      total_minor: 120000,
      currency: "BDT",
      payment_deadline: null,
    }),
    "GET bookings/8a79a96c-c713-477d-8be3-9783eddf4e88/events": (route) => respond(route, []),
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/experiences/e2e-museum-visit/book");
  await expect(page.getByText("No available times on this date. Try another date.")).toBeVisible();
  offerSlot = true;
  const date = new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  await page.getByLabel("Date").fill(date);
  await page.getByRole("button", { name: "10:00 AM" }).click();
  await page.getByLabel("Public venue").fill("Bangladesh National Museum");
  await page.getByLabel("I confirm that I am at least 18 years old.").check();

  const submit = page.getByRole("button", { name: "Send booking request" });
  await submit.click();
  await expect(page.locator("p[role=alert]")).toContainText("Temporary booking error.");
  await submit.click();

  await expect(page).toHaveURL(/\/bookings\/8a79a96c-c713-477d-8be3-9783eddf4e88$/);
  expect(bookingAttempts).toBe(2);
  expect(idempotencyKeys[0]).toBeTruthy();
  expect(idempotencyKeys[1]).toBe(idempotencyKeys[0]);
  expect(slotDate).toBe(date);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test("homepage shows loading and error states and honors reduced motion", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/^\/api\/v1\//, "");
    if (path === "public/marketplace") {
      await new Promise((resolve) => setTimeout(resolve, 350));
      await respond(route, { detail: "Marketplace unavailable." }, 503);
      return;
    }
    await respond(route, emptyPage());
  });

  await page.goto("/");
  await expect(page.getByText("Loading plans…")).toBeVisible();
  await expect(page.getByText("Marketplace unavailable.")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);

  await page.unrouteAll();
  await mockApi(page, {
    "GET public/marketplace": (route) => respond(route, emptyMarketplace()),
    "GET categories": (route) => respond(route, []),
    "GET experiences": (route) => respond(route, emptyPage()),
    "GET companions": (route) => respond(route, emptyPage()),
    "GET collections": (route) => respond(route, emptyPage()),
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Make plans worth remembering." })).toBeVisible();
  const motionContainer = page.getByRole("heading", { name: "Make plans worth remembering." }).locator("xpath=../..");
  await expect.poll(() => motionContainer.evaluate((element) => getComputedStyle(element).transform)).toBe("none");
});

test("sandbox payment failure and success stay labeled and route only after confirmation", async ({ page }) => {
  const failedPaymentId = "2e0c65bc-d41d-4c5c-94c9-9b783986831b";
  const successfulPaymentId = "db1bc4b6-6b41-4b54-a70e-83672370e349";
  const bookingId = "de8d4c02-247d-43e5-a284-5d03758dcc19";
  const payment = (id: string, status = "pending") => ({
    id,
    booking_id: bookingId,
    booking_status: "awaiting_payment",
    status,
    provider: "sandbox",
    provider_label: "Development sandbox — simulated payment only",
    amount_minor: 120000,
    currency: "BDT",
  });
  const booking = {
    id: bookingId,
    conversation_id: null,
    other_party_user_id: null,
    status: "confirmed",
    start_at: "2026-12-01T04:00:00Z",
    end_at: "2026-12-01T05:00:00Z",
    timezone: "Asia/Dhaka",
    experience_title: "Museum visit",
    other_party: "Sample Host",
    viewer_role: "customer",
    public_venue_name: "Bangladesh National Museum",
    customer_note: "",
    total_minor: 120000,
    currency: "BDT",
    payment_deadline: null,
  };

  await mockApi(page, {
    [`GET payments/${failedPaymentId}`]: (route) => respond(route, payment(failedPaymentId)),
    [`POST payments/${failedPaymentId}/sandbox-complete`]: (route) => respond(route, payment(failedPaymentId, "failed")),
    [`GET payments/${successfulPaymentId}`]: (route) => respond(route, payment(successfulPaymentId)),
    [`POST payments/${successfulPaymentId}/sandbox-complete`]: (route) => respond(route, {
      ...payment(successfulPaymentId, "captured"),
      booking_status: "confirmed",
    }),
    [`GET bookings/${bookingId}`]: (route) => respond(route, booking),
    [`GET bookings/${bookingId}/events`]: (route) => respond(route, []),
  });

  await page.goto(`/payments/sandbox/${failedPaymentId}`);
  await expect(page.getByText("Development sandbox — simulated payment only")).toBeVisible();
  await page.getByRole("button", { name: "Simulate payment failure" }).click();
  await expect(page.getByText("failed", { exact: true })).toBeVisible();
  await expect(page.getByText("This payment is no longer awaiting a test outcome.")).toBeVisible();

  await page.goto(`/payments/sandbox/${successfulPaymentId}`);
  await page.getByRole("button", { name: "Simulate successful payment" }).click();
  await expect(page).toHaveURL(new RegExp(`/bookings/${bookingId}$`));
  await expect(page.getByText("Payment was verified and your booking is confirmed.")).toBeVisible();
});
