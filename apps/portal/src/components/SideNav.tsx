"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ITEMS = [
  { href: "/app/onboard", label: "Onboard" },
  { href: "/app/coverage", label: "Cover" },
  { href: "/app/policies", label: "Policies" },
  { href: "/app/trade", label: "Trade" },
  { href: "/app/pool", label: "Pool" },
  { href: "/app/admin", label: "Admin" },
];

export function SideNav() {
  const pathname = usePathname();
  return (
    <nav
      aria-label="App"
      className="flex gap-6 overflow-x-auto border-b border-rule px-6 py-3 md:w-52 md:shrink-0 md:flex-col md:gap-1 md:border-b-0 md:border-r md:px-10 md:py-10"
    >
      {ITEMS.map(({ href, label }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`py-1 text-sm no-underline transition-colors ${
              active ? "text-accent" : "text-muted hover:text-ink"
            }`}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
