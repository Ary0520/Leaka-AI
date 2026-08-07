"use client";

import { usePathname } from "next/navigation";
import { AppShell } from "./app-shell";

// Pages that render without the sidebar/shell
const NO_SHELL_PATHS = ["/login", "/auth"];

export function ConditionalShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const skipShell = NO_SHELL_PATHS.some((p) => pathname?.startsWith(p));

  if (skipShell) {
    return <>{children}</>;
  }

  return <AppShell>{children}</AppShell>;
}
