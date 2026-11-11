"use client";

import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { Footer } from "@/components/layout/footer";
import { Nav } from "@/components/layout/nav";
import { SearchWidget } from "@/components/search/search-widget";
import { Card } from "@/components/ui/card";
import { fetchPublicMarketplaceData, formatPrice, PublicMarketplaceData } from "@/lib/public-data";

export default function ExplorePage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#F7F5F0] px-4 py-20 text-center text-[#20201F]">Loading results…</div>}>
      <ExplorePageContent />
    </Suspense>
  );
}

function ExplorePageContent() {
  const searchParams = useSearchParams();
  const [data, setData] = useState<PublicMarketplaceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const filters = useMemo(
    () => ({
      category: searchParams.get("category") ?? undefined,
      city: searchParams.get("city") ?? undefined,
      date: searchParams.get("date") ?? undefined,
      budget: searchParams.get("budget") ?? undefined,
      q: searchParams.get("q") ?? undefined,
    }),
    [searchParams],
  );

  useEffect(() => {
    let active = true;

    fetchPublicMarketplaceData(filters)
      .then((payload) => {
        if (active) {
          setData(payload);
          setLoading(false);
        }
      })
      .catch((fetchError: Error) => {
        if (active) {
          setError(fetchError.message || "The marketplace request failed.");
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [filters]);

  return (
    <>
      <Nav />
      <main className="min-h-screen bg-[#F7F5F0] text-[#20201F]">
        <section className="mx-auto max-w-6xl px-4 pb-6 pt-10 sm:px-6 lg:px-8">
          <div className="mb-6">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">Explore</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Find the right experience</h1>
          </div>
          {data ? <SearchWidget categories={data.categories} /> : null}
        </section>

        <section className="mx-auto max-w-6xl px-4 pb-16 sm:px-6 lg:px-8">
          {loading ? (
            <div className="rounded-2xl border border-[#E8E4DC] bg-white p-10 text-center text-[#77736D]">
              Loading results…
            </div>
          ) : error ? (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-10 text-center text-red-700">
              {error}
            </div>
          ) : data ? (
            data.experiences.length > 0 ? (
              <div className="grid gap-5 lg:grid-cols-2">
                {data.experiences.map((experience) => (
                  <Link key={experience.id} href={`/experiences/${experience.slug}`}>
                    <Card className="overflow-hidden transition hover:-translate-y-1 hover:shadow-[0_16px_36px_rgba(32,32,31,0.07)]">
                      <div className="grid gap-0 md:grid-cols-[220px_1fr]">
                        <Image
                          src={experience.image}
                          alt={experience.title}
                          width={640}
                          height={420}
                          className="h-full w-full object-cover md:h-[220px]"
                        />
                        <div className="p-5">
                          <div className="flex items-center justify-between gap-3 text-sm text-[#77736D]">
                            <span>{experience.city}</span>
                            <span>{experience.duration_minutes} min</span>
                          </div>
                          <h2 className="mt-3 text-2xl font-semibold text-[#20201F]">{experience.title}</h2>
                          <p className="mt-2 text-sm leading-6 text-[#77736D]">{experience.summary}</p>
                          <div className="mt-4 flex flex-wrap gap-2">
                            {experience.tags.map((tag) => (
                              <span key={tag} className="rounded-full border border-[#E8E4DC] px-2.5 py-1 text-xs text-[#20201F]">
                                {tag}
                              </span>
                            ))}
                          </div>
                          <div className="mt-5 flex items-center justify-between gap-3">
                            <div>
                              <p className="text-xl font-semibold text-[#20201F]">{formatPrice(experience.price_minor, experience.currency)}</p>
                              <p className="text-xs text-[#77736D]">{experience.instant_book ? "Instant booking" : "Request booking"}</p>
                            </div>
                            <div className="rounded-full border border-[#E8E4DC] px-2.5 py-1 text-sm text-[#20201F]">
                              ★ {experience.rating.toFixed(1)}
                            </div>
                          </div>
                        </div>
                      </div>
                    </Card>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-[#E8E4DC] bg-white p-10 text-center text-[#77736D]">
                No experiences match these filters. Try a broader search.
              </div>
            )
          ) : null}
        </section>
      </main>
      <Footer />
    </>
  );
}
