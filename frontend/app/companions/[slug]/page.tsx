"use client";

import Image from "next/image";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Footer } from "@/components/layout/footer";
import { Nav } from "@/components/layout/nav";
import { Card } from "@/components/ui/card";
import { fetchPublicMarketplaceData, PublicMarketplaceData } from "@/lib/public-data";

export default function CompanionDetailPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#F7F5F0] px-4 py-20 text-center text-[#20201F]">Loading host profile…</div>}>
      <CompanionDetailContent />
    </Suspense>
  );
}

function CompanionDetailContent() {
  const params = useParams<{ slug: string }>();
  const [data, setData] = useState<PublicMarketplaceData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    fetchPublicMarketplaceData()
      .then((payload) => {
        if (!active) return;
        setData(payload);
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return <div className="min-h-screen bg-[#F7F5F0] px-4 py-20 text-center text-[#20201F]">Loading host profile…</div>;
  }

  if (!data) {
    return <div className="min-h-screen bg-[#F7F5F0] px-4 py-20 text-center text-red-700">Unable to load host profile.</div>;
  }

  const companion = data.companions.find((item) => item.slug === params.slug) ?? null;

  if (!companion) {
    return (
      <>
        <Nav />
        <main className="min-h-screen bg-[#F7F5F0] px-4 py-20 text-center text-[#20201F] sm:px-6 lg:px-8">Host not found.</main>
        <Footer />
      </>
    );
  }

  const companionExperiences = data.experiences.filter((experience) => experience.host_name === companion.name);

  return (
    <>
      <Nav />
      <main className="bg-[#F7F5F0] text-[#20201F]">
        <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
          <Card className="overflow-hidden p-6">
            <div className="grid gap-6 md:grid-cols-[240px_1fr] md:items-center">
              <Image src={companion.image} alt={companion.name} width={320} height={320} className="h-56 w-full rounded-2xl object-cover" />
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-4xl font-semibold tracking-tight">{companion.name}</h1>
                  {companion.verified ? <span className="rounded-full border border-[#E8E4DC] px-2.5 py-1 text-xs text-[#20201F]">Verified</span> : null}
                </div>
                <p className="mt-3 text-lg text-[#77736D]">{companion.headline}</p>
                <div className="mt-4 flex flex-wrap gap-3 text-sm text-[#20201F]">
                  <span>★ {companion.rating.toFixed(1)}</span>
                  <span>{companion.completed_bookings} bookings</span>
                  <span>{companion.city}</span>
                </div>
                <p className="mt-5 max-w-2xl text-base leading-7 text-[#77736D]">{companion.bio}</p>
                <div className="mt-5 flex flex-wrap gap-2">
                  {companion.tags.map((tag) => (
                    <span key={tag} className="rounded-full bg-[#F7F5F0] px-3 py-1.5 text-xs text-[#20201F]">
                      {tag}
                    </span>
                  ))}
                </div>
                <div className="mt-6 flex gap-3">
                  <Link href="/explore" className="inline-flex items-center justify-center rounded-full bg-[#75404A] px-4 py-2.5 text-sm font-medium text-white transition hover:bg-[#62373d]">
                    Book with {companion.name}
                  </Link>
                  <Link href="/about" className="inline-flex items-center justify-center rounded-full border border-[#E8E4DC] bg-[#F7F5F0] px-4 py-2.5 text-sm font-medium text-[#20201F] transition hover:bg-[#efe9e2]">
                    Message
                  </Link>
                </div>
              </div>
            </div>
          </Card>
        </section>

        <section className="mx-auto max-w-6xl px-4 pb-16 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-semibold tracking-tight">Available plans</h2>
          <div className="mt-5 grid gap-5 md:grid-cols-2">
            {companionExperiences.map((experience) => (
              <Link key={experience.id} href={`/experiences/${experience.slug}`}>
                <Card className="overflow-hidden transition hover:-translate-y-1 hover:shadow-[0_16px_36px_rgba(32,32,31,0.07)]">
                  <Image src={experience.image} alt={experience.title} width={640} height={420} className="h-48 w-full object-cover" />
                  <div className="p-5">
                    <div className="flex items-center justify-between text-sm text-[#77736D]">
                      <span>{experience.city}</span>
                      <span>{experience.duration_minutes} min</span>
                    </div>
                    <h3 className="mt-3 text-xl font-semibold text-[#20201F]">{experience.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-[#77736D]">{experience.summary}</p>
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
