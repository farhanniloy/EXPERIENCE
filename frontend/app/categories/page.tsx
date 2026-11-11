"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Footer } from "@/components/layout/footer";
import { Nav } from "@/components/layout/nav";
import { Card } from "@/components/ui/card";
import { FallbackImage } from "@/components/ui/fallback-image";
import { fetchPublicMarketplaceData, PublicMarketplaceData } from "@/lib/public-data";

export default function CategoriesPage() {
  const [data, setData] = useState<PublicMarketplaceData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    fetchPublicMarketplaceData()
      .then((payload) => {
        if (active) {
          setData(payload);
          setLoading(false);
        }
      })
      .catch(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <>
      <Nav />
      <main className="min-h-screen bg-[#F7F5F0] px-4 py-10 text-[#20201F] sm:px-6 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#75404A]">Categories</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Explore by interest</h1>

          {loading ? (
            <div className="mt-10 rounded-2xl border border-[#E8E4DC] bg-white p-10 text-center text-[#77736D]">
              Loading categories…
            </div>
          ) : data ? (
            <div className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
              {data.categories.map((category) => (
                <Link key={category.slug} href={`/categories/${category.slug}`}>
                  <Card className="overflow-hidden p-5 transition hover:-translate-y-1 hover:shadow-[0_16px_36px_rgba(32,32,31,0.07)]">
                    <FallbackImage
                      src="/placeholder-experience.svg"
                      fallback="/placeholder-experience.svg"
                      alt={category.name}
                      width={640}
                      height={420}
                      className="h-40 w-full rounded-2xl object-cover"
                    />
                    <div className="mt-4 flex items-center justify-between gap-3">
                      <h2 className="text-xl font-semibold text-[#20201F]">{category.name}</h2>
                      <span className="rounded-full border border-[#E8E4DC] px-2.5 py-1 text-xs text-[#77736D]">
                        {category.count} plans
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-[#77736D]">{category.description}</p>
                  </Card>
                </Link>
              ))}
            </div>
          ) : null}
        </div>
      </main>
      <Footer />
    </>
  );
}
