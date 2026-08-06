import type { Metadata } from "next";
import "./globals.css";
import { ReactQueryProvider } from "./providers";
import { AppShell } from "@/components/app-shell";
import { Toaster } from "@/components/ui/toaster";

export const metadata: Metadata = {
  title: "Leaka AI · RevGuard QA",
  description:
    "Autonomous QA agent for e-commerce and SaaS revenue flows using natural language.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background">
        <ReactQueryProvider>
          <AppShell>{children}</AppShell>
          <Toaster />
        </ReactQueryProvider>
      </body>
    </html>
  );
}
