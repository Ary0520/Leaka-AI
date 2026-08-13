import type { Metadata } from "next";
import "./globals.css";
import { ReactQueryProvider } from "./providers";
import { ConditionalShell } from "@/components/conditional-shell";
import { Toaster } from "@/components/ui/toaster";

export const metadata: Metadata = {
  title: "Leaka AI · RevGuard QA",
  description:
    "Autonomous QA agent for e-commerce and SaaS revenue flows using natural language.",
};

import { JetBrains_Mono } from "next/font/google";

const font = JetBrains_Mono({ subsets: ["latin"] });

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`min-h-screen bg-background ${font.className}`}>
        <ReactQueryProvider>
          <ConditionalShell>{children}</ConditionalShell>
          <Toaster />
        </ReactQueryProvider>
      </body>
    </html>
  );
}
