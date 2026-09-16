import type { Metadata } from "next";
import "./globals.css";
import { ReactQueryProvider } from "./providers";
import { ConditionalShell } from "@/components/conditional-shell";
import { Toaster } from "@/components/ui/toaster";

export const metadata: Metadata = {
  metadataBase: new URL("https://www.leaka.live"),
  alternates: {
    canonical: "/",
  },
  title: {
    default: "Leaka AI – Autonomous QA Agent Platform",
    template: "%s | Leaka AI"
  },
  description: "Leaka AI is the enterprise autonomous QA platform. We convert plain English into robust, visual test automation that runs directly in your CI/CD pipeline without maintaining brittle scripts.",
  keywords: ["Autonomous QA", "AI QA Agent", "Software Testing", "Leaka AI", "Test Automation", "Enterprise QA"],
  authors: [{ name: "Leaka AI" }],
  creator: "Leaka AI",
  icons: {
    icon: "/leaka-logo.png",
    apple: "/leaka-logo.png",
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "https://www.leaka.live",
    title: "Leaka AI – Autonomous QA Agent Platform",
    description: "Leaka AI is the enterprise autonomous QA platform. We convert plain English into robust, visual test automation that runs directly in your CI/CD pipeline without maintaining brittle scripts.",
    siteName: "Leaka AI",
    images: [
      {
        url: "https://www.leaka.live/og-image.png",
        width: 1200,
        height: 630,
        alt: "Leaka AI - Autonomous QA Platform",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Leaka AI – Autonomous QA Agent Platform",
    description: "Leaka AI is the enterprise autonomous QA platform. We convert plain English into robust, visual test automation that runs directly in your CI/CD pipeline without maintaining brittle scripts.",
    images: ["https://www.leaka.live/og-image.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
};

import { JetBrains_Mono, Instrument_Sans, Instrument_Serif } from "next/font/google";

const jetbrainsMono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains" });
const instrumentSans = Instrument_Sans({ subsets: ["latin"], variable: "--font-instrument" });
const instrumentSerif = Instrument_Serif({ subsets: ["latin"], weight: "400", variable: "--font-instrument-serif" });

import NextTopLoader from 'nextjs-toploader';

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`min-h-screen bg-background ${instrumentSans.variable} ${instrumentSerif.variable} ${jetbrainsMono.variable} font-sans antialiased`}>
        <NextTopLoader color="#5E6AD2" showSpinner={false} />
        <ReactQueryProvider>
          <ConditionalShell>{children}</ConditionalShell>
          <Toaster />
        </ReactQueryProvider>
      </body>
    </html>
  );
}
