"use client";

import Image from "next/image";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Footer } from "@/components/layout/footer";
import { Nav } from "@/components/layout/nav";
import { Card } from "@/components/ui/card";
import { fetchPublicMarketplaceData, formatPrice, PublicMarketplaceData } from "@/lib/public-data";

export default function ExperienceDetailPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#F7F5F0] px-4 py-20 text-center text-[#20201F]">Loading experience…</div>}>
      <ExperienceDetailContent />
    </Suspense>
  );
}

function ExperienceDetailContent() {
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
    return <div className="min-h-screen bg-[#F7F5F0] px-4 py-20 text-center text-[#20201F]">Loading experience…</div>;
  }

  if (!data) {
    return <div className="min-h-screen bg-[#F7F5F0] px-4 py-20 text-center text-red-700">Unable to load this experience.</div>;
  }

  const experience = data.experiences.find((item) => item.slug === params.slug) ?? null;

  if (!experience) {
    return (
      <>
        <Nav />
        <main className="min-h-screen bg-[#F7F5F0] px-4 py-20 text-center text-[#20201F] sm:px-6 lg:px-8">
          Experience not found.
        </main>
        <Footer />
      </>
    );
  }

  const host = data.companions.find((item) => item.name === experience.host_name) ?? null;

  return (
    <>
      <Nav />
      <main className="bg-[#F7F5F0] text-[#20201F]">
        <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
          <div className="overflow-hidden rounded-[30px] border border-[#E8E4DC] bg-white shadow-sm">
            <Image src={experience.image} alt={experience.title} width={1200} height={640} className="h-[360px] w-full object-cover md:h-[520px]" />
          </div>

          <div className="mt-8 grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
            <div>
              <div className="flex flex-wrap items-center gap-2 text-sm text-[#77736D]">
                <span>{experience.city}</span>
                <span>•</span>
                <span>{experience.duration_minutes} min</span>
                <span>•</span>
                <span>{experience.instant_book ? "Instant booking" : "Request booking"}</span>
              </div>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight">{experience.title}</h1>
              <p className="mt-4 max-w-2xl text-lg leading-8 text-[#77736D]">{experience.description}</p>

              <div className="mt-6 flex flex-wrap gap-2">
                {experience.tags.map((tag) => (
                  <span key={tag} className="rounded-full border border-[#E8E4DC] bg-white px-3 py-1.5 text-xs uppercase tracking-[0.12em] text-[#20201F]">
                    {tag}
                  </span>
                ))}
              </div>
            </div>

            <Card className="h-fit p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">From</p>
              <div className="mt-3 text-4xl font-semibold text-[#20201F]">{formatPrice(experience.price_minor, experience.currency)}</div>
              <p className="mt-2 text-sm text-[#77736D]">Includes safe public venue booking, host guidance, and transparent pricing.</p>
              <div className="mt-6 flex gap-3">
                <Link href="/explore" className="inline-flex flex-1 items-center justify-center rounded-full bg-[#75404A] px-4 py-2.5 text-sm font-medium text-white transition hover:bg-[#62373d]">
                  Reserve now
                </Link>
                <Link href="/about" className="inline-flex flex-1 items-center justify-center rounded-full border border-[#E8E4DC] bg-[#F7F5F0] px-4 py-2.5 text-sm font-medium text-[#20201F] transition hover:bg-[#efe9e2]">
                  Message host
                </Link>
              </div>
              <div className="mt-5 rounded-2xl bg-[#F7F5F0] p-4 text-sm text-[#20201F]">
                <div className="flex items-center justify-between">
                  <span>Rating</span>
                  <span>★ {experience.rating.toFixed(1)}</span>
                </div>
                <div className="mt-2 flex items-center justify-between">
                  <span>Host</span>
                  <span>{experience.host_name}</span>
                </div>
              </div>
            </Card>
          </div>
        </section>

        {host ? (
          <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
            <Card className="p-6">
              <div className="grid gap-6 md:grid-cols-[180px_1fr] md:items-center">
                <Image src={host.image} alt={host.name} width={260} height={260} className="h-44 w-full rounded-2xl object-cover md:h-44" />
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-2xl font-semibold text-[#20201F]">{host.name}</h2>
                    <span className="rounded-full border border-[#E8E4DC] px-2.5 py-1 text-xs text-[#20201F]">Verified</span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-[#77736D]">{host.headline}</p>
                  <div className="mt-4 flex gap-3 text-sm text-[#20201F]">
                    <span>★ {host.rating.toFixed(1)}</span>
                    <span>{host.completed_bookings} bookings</span>
                    <span>{host.city}</span>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {host.tags.map((tag) => (
                      <span key={tag} className="rounded-full bg-[#F7F5F0] px-2.5 py-1 text-xs text-[#20201F]">
                        {tag}
                      </span>
                    ))}
                  </div>
                  <Link href={`/companions/${host.slug}`} className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-[#75404A]">
                    View host profile
                  </Link>
                </div>
              </div>
            </Card>
          </section>
        ) : null}
      </main>
      <Footer />
    </>
  );
}
