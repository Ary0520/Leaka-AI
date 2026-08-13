import type { Metadata } from "next";
import "./globals.css";
import { ReactQueryProvider } from "./providers";
import { ConditionalShell } from "@/components/conditional-shell";
import { Toaster } from "@/components/ui/toaster";

export const metadata: Metadata = {
  title: "Leaka AI",
  description:
    "Autonomous QA agent for e-commerce and SaaS revenue flows using natural language.",
};

import { JetBrains_Mono } from "next/font/google";

const font = JetBrains_Mono({ subsets: ["latin"] });

import NextTopLoader from 'nextjs-toploader';

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`min-h-screen bg-background ${font.className}`}>
        <NextTopLoader color="#5E6AD2" showSpinner={false} />
        <ReactQueryProvider>
          <ConditionalShell>{children}</ConditionalShell>
          <Toaster />
        </ReactQueryProvider>
      </body>
    </html>
  );
}
