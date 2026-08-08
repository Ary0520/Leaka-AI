"use client";

import { usePathname } from "next/navigation";
import { AppShell } from "./app-shell";

// These paths render without the sidebar/shell
const NO_SHELL_PATHS = ["/login", "/auth", "/"];

export function ConditionalShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  // Exact match for "/" (landing), startsWith for /login, /auth
  const skipShell =
    pathname === "/" ||
    NO_SHELL_PATHS.filter((p) => p !== "/").some((p) => pathname?.startsWith(p));

  if (skipShell) {
    return <>{children}</>;
  }

  return <AppShell>{children}</AppShell>;
}
