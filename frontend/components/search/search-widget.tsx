"use client";

import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatPrice, toMinorUnits } from "@/lib/currency";
import { Category } from "@/lib/public-data";

const cityOptions = ["Dhaka", "Chattogram", "Sylhet"];

export function SearchWidget({ categories }: { categories: Category[] }) {
  const router = useRouter();
  const [form, setForm] = useState({
    category: "",
    city: "",
    date: "",
    budget: "",
    q: "",
  });

  const budgetOptions = [1500, 2500, 4000, 6000];

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const params = new URLSearchParams();

    if (form.category) params.set("category", form.category);
    if (form.city) params.set("city", form.city);
    if (form.date) params.set("date", form.date);
    if (form.budget) params.set("budget", form.budget);
    if (form.q) params.set("q", form.q);

    router.push(`/explore${params.toString() ? `?${params.toString()}` : ""}`);
  };

  return (
    <form onSubmit={handleSubmit} className="grid gap-3 rounded-[30px] border border-[#E8E4DC] bg-white p-3 shadow-[0_12px_30px_rgba(32,32,31,0.08)] md:grid-cols-[1.2fr_1fr_1fr_1fr_auto]">
      <div className="rounded-full border border-[#E8E4DC] bg-[#F7F5F0] px-3">
        <label className="sr-only" htmlFor="search-category">Category</label>
        <select
          id="search-category"
          value={form.category}
          onChange={(event) => setForm((current) => ({ ...current, category: event.target.value }))}
          className="h-12 w-full appearance-none bg-transparent pr-2 text-sm text-[#20201F] outline-none"
        >
          <option value="">Any category</option>
          {categories.map((category) => (
            <option key={category.slug} value={category.slug}>
              {category.name}
            </option>
          ))}
        </select>
      </div>

      <div className="rounded-full border border-[#E8E4DC] bg-[#F7F5F0] px-3">
        <label className="sr-only" htmlFor="search-city">City</label>
        <select
          id="search-city"
          value={form.city}
          onChange={(event) => setForm((current) => ({ ...current, city: event.target.value }))}
          className="h-12 w-full appearance-none bg-transparent pr-2 text-sm text-[#20201F] outline-none"
        >
          <option value="">Any city</option>
          {cityOptions.map((city) => (
            <option key={city} value={city}>{city}</option>
          ))}
        </select>
      </div>

      <Input
        type="date"
        value={form.date}
        onChange={(event) => setForm((current) => ({ ...current, date: event.target.value }))}
      />

      <div className="rounded-full border border-[#E8E4DC] bg-[#F7F5F0] px-3">
        <label className="sr-only" htmlFor="search-budget">Budget</label>
        <select
          id="search-budget"
          value={form.budget}
          onChange={(event) => setForm((current) => ({ ...current, budget: event.target.value }))}
          className="h-12 w-full appearance-none bg-transparent pr-2 text-sm text-[#20201F] outline-none"
        >
          <option value="">Any budget</option>
          {budgetOptions.map((option) => (
            <option key={option} value={toMinorUnits(option)}>
              Up to {formatPrice(toMinorUnits(option))}
            </option>
          ))}
        </select>
      </div>

      <Button type="submit" className="gap-2">
        <Search size={16} />
        Search
      </Button>
    </form>
  );
}
