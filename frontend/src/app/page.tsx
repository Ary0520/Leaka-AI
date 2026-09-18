import { Navigation } from "@/components/landing/navigation";
import { HeroSection } from "@/components/landing/hero-section";
import { FeaturesSection } from "@/components/landing/features-section";
import { HowItWorksSection } from "@/components/landing/how-it-works-section";
import { InfrastructureSection } from "@/components/landing/infrastructure-section";
import { MetricsSection } from "@/components/landing/metrics-section";
import { IntegrationsSection } from "@/components/landing/integrations-section";
import { SecuritySection } from "@/components/landing/security-section";
import { DevelopersSection } from "@/components/landing/developers-section";
import { TestimonialsSection } from "@/components/landing/testimonials-section";
import { PricingSection } from "@/components/landing/pricing-section";
import { CtaSection } from "@/components/landing/cta-section";
import { FooterSection } from "@/components/landing/footer-section";

export default function Home() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebSite",
        "@id": "https://www.leaka.live/#website",
        "name": "Leaka AI",
        "alternateName": "Leaka",
        "url": "https://www.leaka.live/",
        "publisher": {
          "@id": "https://www.leaka.live/#organization"
        }
      },
      {
        "@type": "Organization",
        "@id": "https://www.leaka.live/#organization",
        "name": "Leaka AI",
        "url": "https://www.leaka.live/"
      },
      {
        "@type": "SoftwareApplication",
        "@id": "https://www.leaka.live/#software",
        "name": "Leaka AI",
        "url": "https://www.leaka.live/",
        "applicationCategory": "DeveloperApplication",
        "operatingSystem": "Web",
        "description": "Leaka AI is an autonomous QA agent for modern software teams that executes natural-language test flows visually, helps diagnose failures, and supports secure enterprise deployments.",
        "publisher": {
          "@id": "https://www.leaka.live/#organization"
        }
      }
    ]
  };

  return (
    <main className="relative min-h-screen overflow-x-hidden noise-overlay">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <Navigation />
      <HeroSection />
      <HowItWorksSection />
      <FeaturesSection />
      <InfrastructureSection />
      <MetricsSection />
      <IntegrationsSection />
      <SecuritySection />
      <DevelopersSection />
      <TestimonialsSection />
      <PricingSection />
      <CtaSection />
      <FooterSection />
    </main>
  );
}
