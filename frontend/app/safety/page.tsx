import { Footer } from "@/components/layout/footer";
import { Nav } from "@/components/layout/nav";
import { Card } from "@/components/ui/card";

export default function SafetyPage() {
  return (
    <>
      <Nav />
      <main className="min-h-screen bg-[#F7F5F0] px-4 py-12 text-[#20201F] sm:px-6 lg:px-8">
        <div className="mx-auto max-w-4xl">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">Safety</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight">Safety-first by design.</h1>

          <div className="mt-8 grid gap-5">
            <Card className="p-6 text-sm leading-7 text-[#77736D]">
              We maintain adult-only access, verify host profiles, and require safe public venues for in-person plans. We block prohibited activities, share reporting tools, and handle moderation with clear escalation paths.
            </Card>
            <Card className="p-6 text-sm leading-7 text-[#77736D]">
              Any report can be reviewed with supporting context. Users can block and report another person, and bookings can be checked in for a quick safety confirmation before or during the plan.
            </Card>
            <Card className="p-6 text-sm leading-7 text-[#77736D]">
              The marketplace does not permit sexual services, coercion, harassment, or off-platform contact sharing. Profiles and messages can be flagged for moderation.
            </Card>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
