import Link from "next/link";

import { siteConfig } from "@/lib/site-config";

const legalLinks = [
  { href: "/about", label: "About" },
  { href: "/safety", label: "Safety" },
  { href: "/help", label: "Help" },
  { href: "/terms", label: "Terms" },
  { href: "/privacy", label: "Privacy" },
];

export function Footer() {
  return (
    <footer className="border-t border-[#E8E4DC] bg-[#F7F5F0]">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 sm:px-6 lg:grid-cols-[1.3fr_0.7fr_0.8fr] lg:px-8">
        <div>
          <div className="text-2xl font-semibold tracking-tight text-[#20201F]">{siteConfig.brand}</div>
          <p className="mt-3 max-w-md text-sm leading-6 text-[#77736D]">{siteConfig.tagline}</p>
        </div>

        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[#77736D]">Explore</div>
          <ul className="mt-4 space-y-3 text-sm text-[#20201F]">
            <li><Link href="/explore">Explore plans</Link></li>
            <li><Link href="/categories">Browse categories</Link></li>
            <li><Link href="/about">Who we are</Link></li>
          </ul>
        </div>

        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[#77736D]">Policies</div>
          <ul className="mt-4 space-y-3 text-sm text-[#20201F]">
            {legalLinks.map((item) => (
              <li key={item.href}><Link href={item.href}>{item.label}</Link></li>
            ))}
          </ul>
        </div>
      </div>
    </footer>
  );
}
