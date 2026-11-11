import { Footer } from "@/components/layout/footer";
import { Nav } from "@/components/layout/nav";
import { Card } from "@/components/ui/card";

export default function TermsPage() {
  return (
    <>
      <Nav />
      <main className="min-h-screen bg-[#F7F5F0] px-4 py-12 text-[#20201F] sm:px-6 lg:px-8">
        <div className="mx-auto max-w-4xl">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">Terms</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight">Terms of service.</h1>

          <Card className="mt-8 space-y-5 p-6 text-sm leading-7 text-[#77736D]">
            <p>Along connects adults with verified hosts for planned, in-person experiences in public, safe venues.</p>
            <p>Users agree to act respectfully, share only accurate information, and follow all platform safety and verification rules. Hosts and customers are responsible for meeting the local expectations of any booked experience.</p>
            <p>Payments, cancellations, and eligibility are governed by the specific booking terms attached to each experience and the platform policies in effect at that time.</p>
            <p>Along may moderate or remove content that violates safety rules, misuse policies, or local law.</p>
          </Card>
        </div>
      </main>
      <Footer />
    </>
  );
}
