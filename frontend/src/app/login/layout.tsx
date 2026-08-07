// Login page has its own full-screen layout — no sidebar/AppShell
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sign in · Leaka AI",
};

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
