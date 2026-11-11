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

export function formatPrice(value: number, currency = "BDT") {
  return new Intl.NumberFormat("en-BD", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

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

  const response = await fetch(`/api/v1/public/marketplace/${search.toString() ? `?${search.toString()}` : ""}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Marketplace request failed: ${response.status}`);
  }

  return response.json() as Promise<PublicMarketplaceData>;
}
