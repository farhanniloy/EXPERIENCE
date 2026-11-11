import { siteConfig } from "@/lib/site-config";

function currencyDecimalPlaces(currency: string) {
  const fractionDigits = new Intl.NumberFormat("en-BD", {
    style: "currency",
    currency,
  }).resolvedOptions().maximumFractionDigits;
  if (fractionDigits === undefined) {
    throw new Error(`Could not determine the minor-unit scale for ${currency}.`);
  }
  return fractionDigits;
}

export function currencyMinorUnitScale(currency = siteConfig.currency) {
  return 10 ** currencyDecimalPlaces(currency);
}

export function toMinorUnits(value: number, currency = siteConfig.currency) {
  return Math.round(value * currencyMinorUnitScale(currency));
}

export function fromMinorUnits(value: number, currency = siteConfig.currency) {
  return value / currencyMinorUnitScale(currency);
}

export function formatPrice(value: number, currency = siteConfig.currency) {
  const fractionDigits = currencyDecimalPlaces(currency);
  return new Intl.NumberFormat("en-BD", {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: fractionDigits,
  }).format(value / 10 ** fractionDigits);
}
