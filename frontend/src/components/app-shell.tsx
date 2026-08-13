"use client";

import Link from "next/link";
import { ShieldCheck, LayoutDashboard, FileText, Sparkles, Layers, History, Webhook, Settings2, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { usePathname } from "next/navigation";
import React from "react";
import { useAuth } from "@/app/providers";
import { signOut } from "@/lib/api";
import { Button } from "@/components/ui/button";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/runs", label: "All Runs", icon: History },
  { href: "/tests", label: "Test Cases", icon: FileText },
  { href: "/suites", label: "Test Suites", icon: Layers },
  { href: "/new", label: "Run a Test", icon: Sparkles },
  { href: "/ci", label: "CI / CD", icon: Webhook },
  { href: "/settings", label: "Settings", icon: Settings2 },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user } = useAuth();

  return (
    <div className="flex h-screen overflow-hidden">
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
        <nav className="p-3 space-y-1 flex-1 overflow-y-auto">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active =
              item.href === "/dashboard"
                ? pathname === "/dashboard"
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

        {/* User footer */}
        <div className="p-3 border-t space-y-2">
          {user && (
            <div className="px-3 py-2">
              <div className="text-xs font-medium truncate">{user.user_metadata?.full_name || user.email}</div>
              <div className="text-xs text-muted-foreground truncate">{user.email}</div>
            </div>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start gap-2 text-muted-foreground hover:text-destructive"
            onClick={() => signOut()}
          >
            <LogOut className="w-4 h-4" />
            Sign out
          </Button>
          <div className="px-3 text-xs text-muted-foreground">
            Runs locally. No BrowserUse Cloud API required.
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 min-w-0 h-full overflow-y-auto">
        <div className="mx-auto max-w-[1400px] px-4 md:px-8 py-6">
          {children}
        </div>
      </main>
    </div>
  );
}
