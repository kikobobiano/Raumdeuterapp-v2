"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

function navItemActive(pathname: string, href: string): boolean {
  if (href === "/scout/profile") {
    return pathname === "/scout/profile" || pathname.startsWith("/scout/profile/");
  }
  return pathname === href;
}

const SUB_NAV = [
  { href: "/scout/profile", label: "Profile" },
  { href: "/scout/rankings", label: "Rankings" },
  { href: "/scout/scatter", label: "Scatter" },
  { href: "/scout/screener", label: "Screener" },
  { href: "/scout/bar", label: "Bar Chart" },
  { href: "/scout/potential", label: "Potential" },
];

export default function ScoutLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="space-y-6">
      <nav className="flex flex-wrap items-center gap-1 border-b border-outline-variant pb-3">
        {SUB_NAV.map((item) => {
          const active = navItemActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                active
                  ? "bg-primary/15 text-primary"
                  : "text-on-surface-variant hover:bg-surface-mid hover:text-on-surface",
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      {children}
    </div>
  );
}
