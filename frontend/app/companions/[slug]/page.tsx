"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Footer } from "@/components/layout/footer";
import { Nav } from "@/components/layout/nav";
import { Card } from "@/components/ui/card";
import { FallbackImage } from "@/components/ui/fallback-image";
import { fetchPublicMarketplaceData, PublicMarketplaceData } from "@/lib/public-data";
import { apiRequest, jsonBody } from "@/lib/api-client";
import { workflowCopy } from "@/lib/workflow-copy";

type PublicReview = {
  id: string;
  reviewer_name: string;
  rating: number;
  comment: string;
  created_at: string;
  verified_booking: boolean;
};

export default function CompanionDetailPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#F7F5F0] px-4 py-20 text-center text-[#20201F]">{workflowCopy.hostProfileLoading}</div>}>
      <CompanionDetailContent />
    </Suspense>
  );
}

function CompanionDetailContent() {
  const params = useParams<{ slug: string }>();
  const [data, setData] = useState<PublicMarketplaceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [profileError, setProfileError] = useState("");
  const [reviews, setReviews] = useState<PublicReview[] | null>(null);
  const [reviewError, setReviewError] = useState("");
  const [reportingReviewId, setReportingReviewId] = useState("");
  const [reportedReviewIds, setReportedReviewIds] = useState<string[]>([]);
  const [reviewReportError, setReviewReportError] = useState("");

  async function reportReview(reviewId: string, formData: FormData) {
    setReviewReportError("");
    try {
      await apiRequest("reports", {
        method: "POST",
        body: jsonBody({
          review_id: reviewId,
          reason: "review_content",
          description: formData.get("description"),
        }),
      });
      setReportedReviewIds((current) => [...current, reviewId]);
      setReportingReviewId("");
    } catch (reason) {
      setReviewReportError(reason instanceof Error ? reason.message : workflowCopy.reviewReportError);
    }
  }

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
        setProfileError(workflowCopy.reviewProfileError);
        setLoading(false);
      });
    apiRequest<PublicReview[]>(`companions/${encodeURIComponent(params.slug)}/reviews`)
      .then((payload) => {
        if (active) setReviews(payload);
      })
      .catch((reason: unknown) => {
        if (active) setReviewError(reason instanceof Error ? reason.message : workflowCopy.reviewLoadError);
      });

    return () => {
      active = false;
    };
  }, [params.slug]);

  if (loading) {
    return <div className="min-h-screen bg-[#F7F5F0] px-4 py-20 text-center text-[#20201F]">{workflowCopy.hostProfileLoading}</div>;
  }

  if (!data) {
    return <div role="alert" className="min-h-screen bg-[#F7F5F0] px-4 py-20 text-center text-red-700">{profileError || workflowCopy.reviewProfileError}</div>;
  }

  const companion = data.companions.find((item) => item.slug === params.slug) ?? null;

  if (!companion) {
    return (
      <>
        <Nav />
        <main className="min-h-screen bg-[#F7F5F0] px-4 py-20 text-center text-[#20201F] sm:px-6 lg:px-8">{workflowCopy.hostProfileNotFound}</main>
        <Footer />
      </>
    );
  }

  const companionExperiences = data.experiences.filter((experience) =>
    experience.host_slug
      ? experience.host_slug === companion.slug
      : experience.host_name === companion.name,
  );

  return (
    <>
      <Nav />
      <main className="bg-[#F7F5F0] text-[#20201F]">
        <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
          <Card className="overflow-hidden p-6">
            <div className="grid gap-6 md:grid-cols-[240px_1fr] md:items-center">
              <FallbackImage src={companion.image} fallback="/placeholder-host.svg" alt={companion.name} width={320} height={320} className="h-56 w-full rounded-2xl object-cover" />
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
                  <FallbackImage src={experience.image} fallback="/placeholder-experience.svg" alt={experience.title} width={640} height={420} className="h-48 w-full object-cover" />
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
        <section className="mx-auto max-w-6xl px-4 pb-16 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-semibold tracking-tight">{workflowCopy.reviewSectionTitle}</h2>
          {reviewError ? <p role="alert" className="mt-4 text-sm text-red-700">{reviewError}</p> : null}
          {!reviews && !reviewError ? <p className="mt-4 text-sm text-[#77736D]">{workflowCopy.reviewLoading}</p> : null}
          {reviews?.length === 0 ? <p className="mt-4 text-sm text-[#77736D]">{workflowCopy.reviewEmpty}</p> : null}
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            {reviews?.map((review) => (
              <Card key={review.id} className="p-5">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium">{review.reviewer_name}</p>
                  {review.verified_booking ? <span className="rounded-full border border-[#E8E4DC] px-2.5 py-1 text-xs text-[#526044]">{workflowCopy.reviewVerifiedBadge}</span> : null}
                </div>
                <p className="mt-2 text-sm text-[#77736D]">★ {review.rating}/5 · {new Date(review.created_at).toLocaleDateString()}</p>
                {review.comment ? <p className="mt-3 whitespace-pre-wrap text-sm leading-6">{review.comment}</p> : null}
                {reportedReviewIds.includes(review.id) ? <p role="status" className="mt-3 text-sm text-[#526044]">{workflowCopy.reviewReportSent}</p> : (
                  <div className="mt-4">
                    {reportingReviewId === review.id ? (
                      <form action={(formData) => void reportReview(review.id, formData)} className="space-y-3">
                        <label className="block text-sm">{workflowCopy.reviewReportDetails}
                          <textarea name="description" required maxLength={5000} className="mt-2 min-h-20 w-full rounded-lg border border-[#E8E4DC] p-3" />
                        </label>
                        {reviewReportError ? <p role="alert" className="text-sm text-red-700">{reviewReportError}</p> : null}
                        <div className="flex gap-2">
                          <button className="rounded-full bg-[#75404A] px-4 py-2 text-sm text-white">{workflowCopy.safetyReportSubmit}</button>
                          <button type="button" onClick={() => setReportingReviewId("")} className="rounded-full border border-[#E8E4DC] px-4 py-2 text-sm">{workflowCopy.safetyReportCancel}</button>
                        </div>
                      </form>
                    ) : (
                      <button type="button" onClick={() => setReportingReviewId(review.id)} className="text-sm text-[#75404A] underline">{workflowCopy.reviewReportAction}</button>
                    )}
                  </div>
                )}
              </Card>
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
