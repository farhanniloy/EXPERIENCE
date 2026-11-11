"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Footer } from "@/components/layout/footer";
import { Nav } from "@/components/layout/nav";
import { Card } from "@/components/ui/card";
import { FallbackImage } from "@/components/ui/fallback-image";
import { fetchPublicMarketplaceData, formatPrice, PublicMarketplaceData } from "@/lib/public-data";

export default function CategoryDetailPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#F7F5F0] px-4 py-20 text-center text-[#20201F]">Loading category…</div>}>
      <CategoryDetailContent />
    </Suspense>
  );
}

function CategoryDetailContent() {
  const params = useParams<{ slug: string }>();
  const [data, setData] = useState<PublicMarketplaceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    fetchPublicMarketplaceData()
      .then((payload) => {
        if (!active) return;
        setData(payload);
        setLoading(false);
      })
      .catch((fetchError: Error) => {
        if (!active) return;
        setError(fetchError.message || "Unable to load this category.");
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return <div className="min-h-screen bg-[#F7F5F0] px-4 py-20 text-center text-[#20201F]">Loading category…</div>;
  }

  if (!data || error) {
    return <div className="min-h-screen bg-[#F7F5F0] px-4 py-20 text-center text-red-700">{error ?? "No category data found."}</div>;
  }

  const category = data.categories.find((item) => item.slug === params.slug) ?? null;
  const filteredExperiences = data.experiences.filter((experience) => experience.category === params.slug);

  return (
    <>
      <Nav />
      <main className="min-h-screen bg-[#F7F5F0] px-4 py-10 text-[#20201F] sm:px-6 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <div className="rounded-[28px] border border-[#E8E4DC] bg-white p-6 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">Category</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
              {category?.name ?? params.slug}
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-[#77736D]">
              {category?.description ?? "Explore a hand-picked set of activities in this category."}
            </p>
          </div>

          <div className="mt-8 grid gap-5 lg:grid-cols-2">
            {filteredExperiences.length > 0 ? (
              filteredExperiences.map((experience) => (
                <Link key={experience.id} href={`/experiences/${experience.slug}`}>
                  <Card className="overflow-hidden transition hover:-translate-y-1 hover:shadow-[0_16px_36px_rgba(32,32,31,0.07)]">
                    <FallbackImage
                      src={experience.image}
                      fallback="/placeholder-experience.svg"
                      alt={experience.title}
                      width={640}
                      height={420}
                      className="h-52 w-full object-cover"
                    />
                    <div className="p-5">
                      <div className="flex items-center justify-between text-sm text-[#77736D]">
                        <span>{experience.city}</span>
                        <span>{experience.duration_minutes} min</span>
                      </div>
                      <h2 className="mt-3 text-2xl font-semibold text-[#20201F]">{experience.title}</h2>
                      <p className="mt-2 text-sm leading-6 text-[#77736D]">{experience.summary}</p>
                      <div className="mt-5 flex items-center justify-between">
                        <p className="text-xl font-semibold text-[#20201F]">{formatPrice(experience.price_minor, experience.currency)}</p>
                        <span className="rounded-full border border-[#E8E4DC] px-2.5 py-1 text-xs text-[#20201F]">
                          ★ {experience.rating.toFixed(1)}
                        </span>
                      </div>
                    </div>
                  </Card>
                </Link>
              ))
            ) : (
              <div className="rounded-2xl border border-[#E8E4DC] bg-white p-10 text-[#77736D]">
                No experiences available in this category yet.
              </div>
            )}
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
