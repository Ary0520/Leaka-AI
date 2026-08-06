"use client";

import Link from "next/link";
import { ShieldCheck, LayoutDashboard, FileText, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { usePathname } from "next/navigation";
import React from "react";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/tests", label: "Test Cases", icon: FileText },
  { href: "/new", label: "Run a Test", icon: Sparkles },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="hidden md:flex md:w-64 flex-col border-r bg-card/50">
        <div className="px-6 py-5 border-b flex items-center gap-2">
          <div className="w-9 h-9 rounded-lg bg-primary text-primary-foreground grid place-items-center shadow-sm">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div className="leading-tight">
            <div className="font-semibold text-sm">Leaka AI</div>
            <div className="text-xs text-muted-foreground">RevGuard QA</div>
          </div>
        </div>
        <nav className="p-3 space-y-1">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname?.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto p-4 text-xs text-muted-foreground border-t">
          Runs locally. No BrowserUse Cloud API required.
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 min-w-0">
        <div className="mx-auto max-w-[1400px] px-4 md:px-8 py-6">
          {children}
        </div>
      </main>
    </div>
  );
}
