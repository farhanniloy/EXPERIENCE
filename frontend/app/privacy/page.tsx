import { Footer } from "@/components/layout/footer";
import { Nav } from "@/components/layout/nav";
import { Card } from "@/components/ui/card";

export default function PrivacyPage() {
  return (
    <>
      <Nav />
      <main className="min-h-screen bg-[#F7F5F0] px-4 py-12 text-[#20201F] sm:px-6 lg:px-8">
        <div className="mx-auto max-w-4xl">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">Privacy</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight">Privacy and data handling.</h1>

          <Card className="mt-8 space-y-5 p-6 text-sm leading-7 text-[#77736D]">
            <p>Along protects personal information and only uses data required to deliver secure booking, host verification, and customer support.</p>
            <p>Public profiles show general city or area information only. We do not expose residential addresses, private meeting locations, or sensitive identity documents.</p>
            <p>We use cookies and server-side session data to maintain secure account access and trust-related activity. Details are handled according to platform policy and applicable privacy obligations.</p>
            <p>Users can manage communication preferences, report concerns, and request support for their account information.</p>
          </Card>
        </div>
      </main>
      <Footer />
    </>
  );
}
