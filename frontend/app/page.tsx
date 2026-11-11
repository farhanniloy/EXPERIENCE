"use client";

import Image from "next/image";
import Link from "next/link";
import { ArrowRight, CalendarCheck2, MapPin, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { Footer } from "@/components/layout/footer";
import { Nav } from "@/components/layout/nav";
import { SearchWidget } from "@/components/search/search-widget";
import { Card } from "@/components/ui/card";
import { FadeIn } from "@/components/ui/motion";
import { fetchPublicMarketplaceData, formatPrice, PublicMarketplaceData } from "@/lib/public-data";

export default function HomePage() {
  const [data, setData] = useState<PublicMarketplaceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    fetchPublicMarketplaceData()
      .then((payload) => {
        if (active) {
          setData(payload);
          setLoading(false);
        }
      })
      .catch((fetchError: Error) => {
        if (active) {
          setError(fetchError.message || "Unable to load the marketplace.");
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#F7F5F0] px-4 py-20 text-center text-[#20201F]">
        <p className="text-lg font-medium">Loading plans…</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-[#F7F5F0] px-4 py-20 text-center text-[#20201F]">
        <p className="text-lg font-medium text-red-700">{error ?? "No marketplace data available."}</p>
      </div>
    );
  }

  const featuredExperiences = data.experiences.slice(0, 3);
  const featuredCompanions = data.companions.slice(0, 3);

  return (
    <>
      <Nav />
      <main className="bg-[#F7F5F0] text-[#20201F]">
        <section className="mx-auto max-w-6xl px-4 pb-10 pt-12 sm:px-6 lg:px-8 lg:pt-16">
          <div className="grid items-center gap-10 lg:grid-cols-[1.1fr_0.9fr]">
            <FadeIn>
              <div>
                <p className="mb-4 inline-flex items-center rounded-full border border-[#E8E4DC] bg-white px-3 py-1 text-[11px] font-medium uppercase tracking-[0.2em] text-[#75404A]">
                  Bangladesh · {data.site.city}
                </p>
                <h1 className="max-w-xl text-4xl font-semibold tracking-[-0.04em] text-[#20201F] sm:text-5xl lg:text-6xl">
                  Make plans worth remembering.
                </h1>
                <p className="mt-5 max-w-lg text-lg leading-8 text-[#77736D]">
                  Thoughtful experiences designed for easy conversation, safe meeting spots, and memorable city moments.
                </p>
                <div className="mt-7 flex flex-wrap gap-3">
                  <Link href="/explore" className="inline-flex items-center gap-2 rounded-full bg-[#75404A] px-5 py-3 text-sm font-medium text-white transition hover:bg-[#62373d]">
                    Explore experiences
                    <ArrowRight size={16} />
                  </Link>
                  <Link href="/categories" className="inline-flex items-center gap-2 rounded-full border border-[#E8E4DC] bg-white px-5 py-3 text-sm font-medium text-[#20201F] transition hover:bg-[#efe9e2]">
                    Browse categories
                  </Link>
                </div>
              </div>
            </FadeIn>

            <FadeIn className="relative">
              <div className="overflow-hidden rounded-[32px] border border-[#E8E4DC] bg-white p-4 shadow-[0_24px_60px_rgba(32,32,31,0.08)]">
                <Image
                  src="/placeholder-experience.svg"
                  alt="Illustrated social experience in Dhaka"
                  width={760}
                  height={720}
                  className="h-[440px] w-full rounded-[24px] object-cover"
                  priority
                />
                <div className="mt-4 flex items-center justify-between gap-4 rounded-2xl bg-[#F7F5F0] p-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-[#77736D]">Popular now</p>
                    <p className="mt-2 text-lg font-medium text-[#20201F]">Dhaka evening walk</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs uppercase tracking-[0.2em] text-[#77736D]">From</p>
                    <p className="mt-2 text-xl font-semibold text-[#20201F]">৳1,900</p>
                  </div>
                </div>
              </div>
            </FadeIn>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 pb-8 sm:px-6 lg:px-8">
          <SearchWidget categories={data.categories} />
        </section>

        <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="mb-6 flex items-end justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">Browse</p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight">Popular categories</h2>
            </div>
            <Link href="/categories" className="text-sm font-medium text-[#75404A]">
              See all
            </Link>
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {data.categories.slice(0, 6).map((category) => (
              <Link key={category.slug} href={`/categories/${category.slug}`}>
                <Card className="h-full p-5 transition hover:-translate-y-0.5 hover:shadow-[0_16px_36px_rgba(32,32,31,0.06)]">
                  <div className="flex items-center justify-between">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#F7F5F0] text-[#75404A]">
                      <Sparkles size={20} />
                    </div>
                    <span className="rounded-full border border-[#E8E4DC] px-2.5 py-1 text-xs text-[#77736D]">
                      {category.count} plans
                    </span>
                  </div>
                  <h3 className="mt-5 text-xl font-semibold text-[#20201F]">{category.name}</h3>
                  <p className="mt-2 text-sm leading-6 text-[#77736D]">{category.description}</p>
                </Card>
              </Link>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="mb-6 flex items-end justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">Curated</p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight">Plans worth sharing</h2>
            </div>
          </div>

          <div className="grid gap-5 lg:grid-cols-3">
            {data.collections.map((collection) => (
              <Card key={collection.slug} className="overflow-hidden">
                <Image
                  src={collection.image}
                  alt={collection.title}
                  width={640}
                  height={420}
                  className="h-48 w-full object-cover"
                />
                <div className="p-5">
                  <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-[#77736D]">
                    <MapPin size={14} />
                    {collection.city}
                  </div>
                  <h3 className="mt-3 text-xl font-semibold text-[#20201F]">{collection.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-[#77736D]">{collection.description}</p>
                  <Link href="/explore" className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-[#75404A]">
                    Explore collection <ArrowRight size={16} />
                  </Link>
                </div>
              </Card>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="mb-6 flex items-end justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">Featured</p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight">Recommended experiences</h2>
            </div>
          </div>

          <div className="grid gap-5 lg:grid-cols-3">
            {featuredExperiences.map((experience) => (
              <Link key={experience.id} href={`/experiences/${experience.slug}`}>
                <Card className="overflow-hidden transition hover:-translate-y-1 hover:shadow-[0_16px_36px_rgba(32,32,31,0.07)]">
                  <Image
                    src={experience.image}
                    alt={experience.title}
                    width={640}
                    height={420}
                    className="h-52 w-full object-cover"
                  />
                  <div className="p-5">
                    <div className="flex items-center justify-between gap-3 text-sm text-[#77736D]">
                      <span>{experience.city}</span>
                      <span>{experience.duration_minutes} min</span>
                    </div>
                    <h3 className="mt-3 text-xl font-semibold text-[#20201F]">{experience.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-[#77736D]">{experience.summary}</p>
                    <div className="mt-4 flex items-center justify-between gap-3">
                      <div>
                        <p className="text-[#20201F] font-semibold">{formatPrice(experience.price_minor, experience.currency)}</p>
                        <p className="text-xs text-[#77736D]">{experience.instant_book ? "Instant booking" : "Request booking"}</p>
                      </div>
                      <div className="rounded-full border border-[#E8E4DC] px-2.5 py-1 text-sm text-[#20201F]">
                        ★ {experience.rating.toFixed(1)}
                      </div>
                    </div>
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="mb-6 flex items-end justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">Hosts</p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight">Meet local hosts</h2>
            </div>
          </div>

          <div className="grid gap-5 md:grid-cols-3">
            {featuredCompanions.map((companion) => (
              <Link key={companion.id} href={`/companions/${companion.slug}`}>
                <Card className="p-5 transition hover:-translate-y-1 hover:shadow-[0_16px_36px_rgba(32,32,31,0.07)]">
                  <Image
                    src={companion.image}
                    alt={companion.name}
                    width={420}
                    height={420}
                    className="h-52 w-full rounded-2xl object-cover"
                  />
                  <div className="mt-4 flex items-center justify-between">
                    <p className="text-xl font-semibold text-[#20201F]">{companion.name}</p>
                    {companion.verified ? <ShieldCheck size={18} className="text-[#75404A]" /> : null}
                  </div>
                  <p className="mt-2 text-sm text-[#77736D]">{companion.headline}</p>
                  <div className="mt-4 flex items-center justify-between text-sm text-[#20201F]">
                    <span>{companion.city}</span>
                    <span>★ {companion.rating.toFixed(1)}</span>
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="grid gap-5 rounded-[28px] border border-[#E8E4DC] bg-[#F7F5F0] p-7 md:grid-cols-3">
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-full bg-[#75404A] text-white">
                <CalendarCheck2 size={18} />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-[#20201F]">Easy bookings</h3>
                <p className="mt-2 text-sm leading-6 text-[#77736D]">Clear pricing, safe meetings, and instant or request-based plans.</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-full bg-[#75404A] text-white">
                <MapPin size={18} />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-[#20201F]">City-first curation</h3>
                <p className="mt-2 text-sm leading-6 text-[#77736D]">Curated experiences in Dhaka, Chattogram, and beyond.</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-full bg-[#75404A] text-white">
                <ShieldCheck size={18} />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-[#20201F]">Verified, safe, adults-only</h3>
                <p className="mt-2 text-sm leading-6 text-[#77736D]">Every listing follows moderation, safety, and public-venue rules.</p>
              </div>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
