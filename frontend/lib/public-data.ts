import { apiRequest } from "@/lib/api-client";

export { formatPrice } from "@/lib/currency";

export type SiteData = {
  brand: string;
  tagline: string;
  currency: string;
  timezone: string;
  country: string;
  city: string;
};

export type Category = {
  id: string;
  slug: string;
  name: string;
  description: string;
  icon: string;
  count: number;
  featured?: boolean;
};

export type Experience = {
  id: string;
  slug: string;
  title: string;
  city: string;
  summary: string;
  description: string;
  price_minor: number;
  currency: string;
  duration_minutes: number;
  category: string;
  rating: number;
  instant_book: boolean;
  host_name: string;
  host_slug?: string;
  image: string;
  tags: string[];
};

export type Companion = {
  id: string;
  slug: string;
  name: string;
  city: string;
  headline: string;
  bio: string;
  rating: number;
  completed_bookings: number;
  verified: boolean;
  image: string;
  tags: string[];
};

export type Collection = {
  id: string;
  slug: string;
  title: string;
  description: string;
  city: string;
  image: string;
  experience_ids: string[];
};

export type PublicMarketplaceData = {
  site: SiteData;
  categories: Category[];
  experiences: Experience[];
  companions: Companion[];
  collections: Collection[];
};

type Page<T> = { results: T[] };
type DatabaseCategory = Category;
type DatabaseHost = {
  id: string;
  slug: string;
  name: string;
  city: string;
  headline: string;
  biography: string;
  rating: string | number;
  completed_bookings: number;
  verified: boolean;
  image: string;
  photos: string[];
  interests: string[];
};
type DatabaseExperience = {
  id: string;
  slug: string;
  title: string;
  summary: string;
  description: string;
  city: string;
  host: DatabaseHost;
  host_name: string;
  price_minor: number;
  currency: string;
  duration_minutes: number;
  category: string;
  rating: string | number;
  instant_booking_enabled: boolean;
  image: string;
  tags: string[];
};
type DatabaseCollection = {
  id: string;
  slug: string;
  title: string;
  description: string;
  city: string;
  image: string;
  experiences: DatabaseExperience[];
};

export async function fetchPublicMarketplaceData(
  params: Record<string, string | string[] | null | undefined> = {},
): Promise<PublicMarketplaceData> {
  const search = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (!value) {
      return;
    }

    if (Array.isArray(value)) {
      value.forEach((item) => item && search.append(key, item));
      return;
    }

    search.append(key, value);
  });

  const suffix = search.toString() ? `?${search.toString()}` : "";
  const [fixture, categories, experiencePage, hostPage, collectionPage] = await Promise.all([
    apiRequest<PublicMarketplaceData>(`public/marketplace${suffix}`),
    apiRequest<DatabaseCategory[]>("categories"),
    apiRequest<Page<DatabaseExperience>>(`experiences${suffix}`),
    apiRequest<Page<DatabaseHost>>("companions"),
    apiRequest<Page<DatabaseCollection>>("collections"),
  ]);

  const companions = new Map(fixture.companions.map((host) => [host.slug, host]));
  hostPage.results.forEach((host) => {
    companions.set(host.slug, {
      id: host.id,
      slug: host.slug,
      name: host.name,
      city: host.city,
      headline: host.headline,
      bio: host.biography,
      rating: Number(host.rating),
      completed_bookings: host.completed_bookings,
      verified: host.verified,
      image: host.photos[0] ?? host.image,
      tags: host.interests,
    });
  });

  const experiences = new Map(fixture.experiences.map((item) => [item.slug, item]));
  experiencePage.results.forEach((item) => {
    experiences.set(item.slug, {
      id: item.id,
      slug: item.slug,
      title: item.title,
      city: item.city,
      summary: item.summary,
      description: item.description,
      price_minor: item.price_minor,
      currency: item.currency,
      duration_minutes: item.duration_minutes,
      category: item.category,
      rating: Number(item.rating),
      instant_book: item.instant_booking_enabled,
      host_name: item.host_name,
      host_slug: item.host.slug,
      image: item.image,
      tags: item.tags,
    });
  });

  const mergedCategories = new Map(fixture.categories.map((item) => [item.slug, item]));
  categories.forEach((category) => mergedCategories.set(category.slug, category));

  const collections = new Map(fixture.collections.map((item) => [item.slug, item]));
  collectionPage.results.forEach((item) => {
    collections.set(item.slug, {
      id: item.id,
      slug: item.slug,
      title: item.title,
      description: item.description,
      city: item.city,
      image: item.image,
      experience_ids: item.experiences.map((experience) => experience.id),
    });
  });

  return {
    ...fixture,
    categories: [...mergedCategories.values()],
    experiences: [...experiences.values()],
    companions: [...companions.values()],
    collections: [...collections.values()],
  };
}
