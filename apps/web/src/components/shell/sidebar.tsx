"use client";

import {
  BarChart3,
  LayoutDashboard,
  type LucideIcon,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Trophy,
  Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";
import { useSidebar } from "@/lib/sidebar-store";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const NAV: NavItem[] = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/scout", label: "Player Scout", icon: Users },
  { href: "/teams", label: "Team Metrics", icon: Trophy },
  { href: "/glossary", label: "Glossary", icon: BarChart3 },
];

export function Sidebar() {
  const pathname = usePathname();
  const collapsed = useSidebar((s) => s.collapsed);
  const toggle = useSidebar((s) => s.toggle);

  return (
    <aside
      className={cn(
        "flex shrink-0 flex-col border-r border-outline-variant bg-surface-low transition-[width] duration-200",
        collapsed ? "w-16" : "w-60",
      )}
    >
      <div
        className={cn(
          "flex items-start justify-between px-3 pt-4 pb-6",
          collapsed && "px-2",
        )}
      >
        {!collapsed && (
          <div className="px-3">
            <p className="font-mono text-xs font-bold uppercase tracking-[0.2em] text-primary">
              Raumdeuter
            </p>
            <p className="font-mono text-xs font-bold uppercase tracking-[0.2em] text-on-surface">
              App
            </p>
            <p className="mt-2 text-[10px] uppercase tracking-wider text-on-surface-variant">
              Elite Performance Data
            </p>
          </div>
        )}
        <button
          type="button"
          onClick={toggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={cn(
            "grid h-8 w-8 place-items-center rounded-md text-on-surface-variant hover:bg-surface-mid hover:text-on-surface",
            collapsed && "mx-auto",
          )}
        >
          {collapsed ? (
            <PanelLeftOpen className="h-4 w-4" strokeWidth={1.5} />
          ) : (
            <PanelLeftClose className="h-4 w-4" strokeWidth={1.5} />
          )}
        </button>
      </div>

      <nav className={cn("flex-1 space-y-1", collapsed ? "px-2" : "px-3")}>
        {NAV.map((item) => {
          const active =
            item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              title={collapsed ? item.label : undefined}
              className={cn(
                "flex items-center gap-3 rounded-md text-sm font-medium transition-colors",
                collapsed ? "justify-center px-2 py-2" : "px-3 py-2",
                active
                  ? "bg-primary/10 text-primary"
                  : "text-on-surface-variant hover:bg-surface-mid hover:text-on-surface",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" strokeWidth={1.5} />
              {!collapsed && <span>{item.label}</span>}
              {!collapsed && active && (
                <span className="ml-auto h-1.5 w-1.5 rounded-full bg-primary" />
              )}
            </Link>
          );
        })}
      </nav>

      <div className={cn("pb-3", collapsed ? "px-2" : "px-3")}>
        <Link
          href="/settings"
          title={collapsed ? "Settings" : undefined}
          className={cn(
            "flex items-center gap-3 rounded-md text-sm text-on-surface-variant hover:bg-surface-mid",
            collapsed ? "justify-center px-2 py-2" : "px-3 py-2",
          )}
        >
          <Settings className="h-4 w-4 shrink-0" strokeWidth={1.5} />
          {!collapsed && <span>Settings</span>}
        </Link>
      </div>

      {!collapsed && (
        <div className="border-t border-outline-variant p-4">
          <Button variant="primary" size="md" className="w-full uppercase tracking-wider text-xs">
            Generate Report
          </Button>
        </div>
      )}
    </aside>
  );
}
