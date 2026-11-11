import { Footer } from "@/components/layout/footer";
import { Nav } from "@/components/layout/nav";
import { Card } from "@/components/ui/card";

const helpTopics = [
  {
    title: "Booking and payments",
    description: "You can browse experiences, request a plan, and complete payment through the secure booking flow. Booking requests are confirmed only after host acceptance and server-side verification.",
  },
  {
    title: "Safety and trust",
    description: "All meetings should take place at public venues. You can view host verification, read public reviews, and report any concerns directly from your booking or profile.",
  },
  {
    title: "Account support",
    description: "Need help updating your profile, resetting a password, or understanding a booking status? Support can help you through the account and moderation flow.",
  },
];

export default function HelpPage() {
  return (
    <>
      <Nav />
      <main className="min-h-screen bg-[#F7F5F0] px-4 py-12 text-[#20201F] sm:px-6 lg:px-8">
        <div className="mx-auto max-w-4xl">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">Help</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight">Support for every plan.</h1>

          <div className="mt-8 grid gap-5">
            {helpTopics.map((topic) => (
              <Card key={topic.title} className="p-6">
                <h2 className="text-xl font-semibold text-[#20201F]">{topic.title}</h2>
                <p className="mt-3 text-sm leading-7 text-[#77736D]">{topic.description}</p>
              </Card>
            ))}
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
