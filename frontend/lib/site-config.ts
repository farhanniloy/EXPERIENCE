export const siteConfig = {
  brand: process.env.NEXT_PUBLIC_BRAND_NAME ?? "Along",
  tagline: process.env.NEXT_PUBLIC_TAGLINE ?? "Good company. Great experiences.",
  countryCode: process.env.NEXT_PUBLIC_COUNTRY_CODE ?? "BD",
  currency: process.env.NEXT_PUBLIC_CURRENCY_CODE ?? "BDT",
  timezone: process.env.NEXT_PUBLIC_TIME_ZONE ?? "Asia/Dhaka",
  city: process.env.NEXT_PUBLIC_LAUNCH_CITY ?? "Dhaka",
};
