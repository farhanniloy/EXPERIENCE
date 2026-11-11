import Link from "next/link";

import { Footer } from "@/components/layout/footer";
import { Nav } from "@/components/layout/nav";
import { Card } from "@/components/ui/card";

export default function AboutPage() {
  return (
    <>
      <Nav />
      <main className="min-h-screen bg-[#F7F5F0] px-4 py-12 text-[#20201F] sm:px-6 lg:px-8">
        <div className="mx-auto max-w-4xl">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">About</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight">A better way to make plans.</h1>
          <Card className="mt-8 p-6 text-base leading-8 text-[#77736D]">
            Along helps adults book meaningful, safe, and memorable experiences with trusted local hosts. Our focus is on thoughtful planning, public venue meetups, and clear communication from start to finish.
            <div className="mt-5 space-y-3">
              <p>We prioritize safety, privacy, and transparent pricing for every interaction.</p>
              <p>Hosts can build a profile, share interests, and offer city-first experiences. Customers can browse, compare, and book with confidence.</p>
            </div>
          </Card>

          <div className="mt-8 grid gap-5 md:grid-cols-2">
            <Card className="p-6">
              <h2 className="text-xl font-semibold text-[#20201F]">Our promise</h2>
              <p className="mt-3 text-sm leading-7 text-[#77736D]">Every plan should be easy to trust, easy to join, and easy to enjoy.</p>
            </Card>
            <Card className="p-6">
              <h2 className="text-xl font-semibold text-[#20201F]">Launch market</h2>
              <p className="mt-3 text-sm leading-7 text-[#77736D]">Bangladesh, BDT, and Asia/Dhaka are part of the central product configuration for the MVP.</p>
            </Card>
          </div>

          <div className="mt-8 text-sm text-[#20201F]">
            <Link href="/explore" className="font-medium text-[#75404A]">Start exploring</Link>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
