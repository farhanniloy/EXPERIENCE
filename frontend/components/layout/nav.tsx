"use client";

import Link from "next/link";
import { Menu, Search, X } from "lucide-react";
import { useState } from "react";

import { siteConfig } from "@/lib/site-config";

const navItems = [
  { label: "Explore", href: "/explore" },
  { label: "Categories", href: "/categories" },
  { label: "About", href: "/about" },
  { label: "Safety", href: "/safety" },
];

export function Nav() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-[#E8E4DC] bg-white/90 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-center gap-3 text-[#20201F]">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#75404A] text-sm font-semibold text-white">
            A
          </div>
          <div>
            <div className="text-lg font-semibold tracking-tight">{siteConfig.brand}</div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-[#77736D]">{siteConfig.tagline}</div>
          </div>
        </Link>

        <nav className="hidden items-center gap-6 md:flex">
          {navItems.map((item) => (
            <Link key={item.href} href={item.href} className="text-sm text-[#20201F] hover:text-[#75404A]">
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          <Link href="/explore" className="inline-flex items-center justify-center gap-2 rounded-full border border-[#E8E4DC] bg-[#F7F5F0] px-4 py-2.5 text-sm font-medium text-[#20201F] transition hover:bg-[#efe9e2]">
            <Search size={16} />
            Find plans
          </Link>
          <Link href="/about" className="inline-flex items-center justify-center rounded-full bg-[#75404A] px-4 py-2.5 text-sm font-medium text-white transition hover:bg-[#62373d]">
            Become a host
          </Link>
        </div>

        <button
          type="button"
          className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[#E8E4DC] md:hidden"
          aria-label="Toggle menu"
          onClick={() => setMobileOpen((value) => !value)}
        >
          {mobileOpen ? <X size={18} /> : <Menu size={18} />}
        </button>
      </div>

      {mobileOpen ? (
        <div className="border-t border-[#E8E4DC] bg-white md:hidden">
          <nav className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-4">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="text-sm text-[#20201F]"
                onClick={() => setMobileOpen(false)}
              >
                {item.label}
              </Link>
            ))}
            <Link href="/about" className="inline-flex w-full items-center justify-center rounded-full bg-[#75404A] px-4 py-2.5 text-sm font-medium text-white transition hover:bg-[#62373d]" onClick={() => setMobileOpen(false)}>
              Become a host
            </Link>
          </nav>
        </div>
      ) : null}
    </header>
  );
}
