"use client";

import { useState, useRef } from "react";
import { ArrowRight, Check, Loader2 } from "lucide-react";
import { joinWaitlist } from "@/app/actions/waitlist";

const plans = [
  {
    name: "Starter",
    description: "For individuals and small projects",
    price: { monthly: 0, annual: 0 },
    features: [
      "Up to 3 projects",
      "10 test runs per month",
      "Community support",
      "Basic analytics",
      "Self-healing execution",
    ],
    cta: "Start free",
    popular: false,
  },
  {
    name: "Pro",
    description: "For growing teams and businesses",
    price: { monthly: 29, annual: 24 },
    features: [
      "Unlimited projects",
      "500 test runs per month",
      "Priority support",
      "Visual proof & RCA",
      "Linear/Jira Auto-ticketing",
      "Team collaboration",
      "API access & Webhooks",
    ],
    cta: "Start trial",
    popular: true,
  },
  {
    name: "Enterprise",
    description: "For large-scale operations",
    price: { monthly: null, annual: null },
    features: [
      "Everything in Pro",
      "Unlimited test runs",
      "24/7 dedicated support",
      "Custom integrations",
      "SLA guarantee",
      "VPC / On-premise deployment",
      "SOC2 Compliance reporting",
      "RBAC & Advanced Security",
    ],
    cta: "Contact sales",
    popular: false,
  },
];

export function PricingSection() {
  const [isAnnual, setIsAnnual] = useState(true);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const formRef = useRef<HTMLFormElement>(null);

  async function handleWaitlist(formData: FormData) {
    setStatus("loading");
    const result = await joinWaitlist(formData);
    if (result.success) {
      setStatus("success");
      formRef.current?.reset();
    } else {
      setStatus("error");
    }
  }

  return (
    <section id="pricing" className="relative py-32 lg:py-40 border-t border-foreground/10">
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        {/* Header */}
        <div className="max-w-3xl mb-20">
          <span className="font-mono text-xs tracking-widest text-muted-foreground uppercase block mb-6">
            Pricing
          </span>
          <h2 className="font-display text-5xl md:text-6xl lg:text-7xl tracking-tight text-foreground mb-6">
            Simple, transparent
            <br />
            <span className="text-stroke">pricing</span>
          </h2>
          <p className="text-lg text-muted-foreground max-w-xl">
            Start free and scale as you grow. No hidden fees, no surprises.
          </p>
        </div>

        {/* Waitlist CTA Area */}
        <div className="bg-foreground/5 border border-foreground/10 p-8 md:p-12 max-w-3xl mx-auto flex flex-col items-center text-center relative overflow-hidden">
          <div className="relative z-10 w-full flex flex-col items-center">
            <h3 className="font-display text-2xl md:text-3xl text-foreground mb-4">
              Join the exclusive waitlist
            </h3>
            <p className="text-muted-foreground mb-8 max-w-md">
              We are currently onboarding enterprise partners in batches to ensure maximum quality and dedicated support.
            </p>
            
            <div className="w-full max-w-md min-h-[60px] relative flex justify-center">
              {status === "success" ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center animate-in fade-in zoom-in duration-500">
                  <div className="w-full bg-primary/10 border border-primary/20 text-primary-foreground px-6 py-4 flex items-center justify-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
                      <Check className="w-4 h-4 text-primary" />
                    </div>
                    <span className="font-medium text-sm">Status Confirmed. Check your inbox.</span>
                  </div>
                </div>
              ) : (
                <form 
                  ref={formRef} 
                  action={handleWaitlist} 
                  className={`w-full flex flex-col sm:flex-row gap-3 absolute inset-0 transition-all duration-500 ${
                    status === "loading" ? "opacity-70 scale-[0.98]" : "opacity-100 scale-100"
                  }`}
                >
                  <input 
                    name="email"
                    type="email" 
                    placeholder="Enter your work email" 
                    className="flex-1 px-4 py-3 bg-background border border-foreground/20 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-foreground transition-colors"
                    required
                    disabled={status === "loading"}
                  />
                  <button 
                    type="submit" 
                    disabled={status === "loading"}
                    className="px-6 py-3 bg-foreground text-background font-medium hover:bg-foreground/90 transition-all flex items-center justify-center gap-2 group disabled:cursor-not-allowed"
                  >
                    {status === "loading" ? "Securing spot..." : "Join Waitlist"}
                    {status === "loading" ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
                    )}
                  </button>
                </form>
              )}
            </div>

            {status === "error" && (
              <p className="text-red-500 text-sm mt-4 animate-in fade-in">Something went wrong. Please try again.</p>
            )}

            <div className="flex items-center gap-4 w-full max-w-md mt-10 mb-6 transition-opacity duration-500">
              <div className="h-px bg-foreground/10 flex-1"></div>
              <span className="text-xs text-muted-foreground uppercase tracking-widest font-mono">OR</span>
              <div className="h-px bg-foreground/10 flex-1"></div>
            </div>

            <a 
              href="mailto:founder@leaka.live" 
              className="px-6 py-3 border border-foreground/20 text-foreground font-medium hover:bg-foreground/5 hover:border-foreground transition-all"
            >
              Talk to Founder
            </a>
          </div>
          
          {/* Subtle background glow when success */}
          <div className={`absolute inset-0 bg-primary/5 transition-opacity duration-1000 ${status === "success" ? "opacity-100" : "opacity-0"}`} />
        </div>

        {/* 
        =========================================
        PRICING CARDS - COMMENTED OUT FOR NOW
        =========================================
        <div className="flex items-center gap-4 mb-16">
          <span
            className={`text-sm transition-colors ${
              !isAnnual ? "text-foreground" : "text-muted-foreground"
            }`}
          >
            Monthly
          </span>
          <button
            onClick={() => setIsAnnual(!isAnnual)}
            className="relative w-14 h-7 bg-foreground/10 rounded-full p-1 transition-colors hover:bg-foreground/20"
          >
            <div
              className={`w-5 h-5 bg-foreground rounded-full transition-transform duration-300 ${
                isAnnual ? "translate-x-7" : "translate-x-0"
              }`}
            />
          </button>
          <span
            className={`text-sm transition-colors ${
              isAnnual ? "text-foreground" : "text-muted-foreground"
            }`}
          >
            Annual
          </span>
          {isAnnual && (
            <span className="ml-2 px-2 py-1 bg-foreground text-primary-foreground text-xs font-mono">
              Save 17%
            </span>
          )}
        </div>

        <div className="grid md:grid-cols-3 gap-px bg-foreground/10">
          {plans.map((plan, idx) => (
            <div
              key={plan.name}
              className={`relative p-8 lg:p-12 bg-background ${
                plan.popular ? "md:-my-4 md:py-12 lg:py-16 border-2 border-foreground" : ""
              }`}
            >
              {plan.popular && (
                <span className="absolute -top-3 left-8 px-3 py-1 bg-foreground text-primary-foreground text-xs font-mono uppercase tracking-widest">
                  Most Popular
                </span>
              )}

              <div className="mb-8">
                <span className="font-mono text-xs text-muted-foreground">
                  {String(idx + 1).padStart(2, "0")}
                </span>
                <h3 className="font-display text-3xl text-foreground mt-2">{plan.name}</h3>
                <p className="text-sm text-muted-foreground mt-2">{plan.description}</p>
              </div>

              <div className="mb-8 pb-8 border-b border-foreground/10">
                {plan.price.monthly !== null ? (
                  <div className="flex items-baseline gap-2">
                    <span className="font-display text-5xl lg:text-6xl text-foreground">
                      ${isAnnual ? plan.price.annual : plan.price.monthly}
                    </span>
                    <span className="text-muted-foreground">/month</span>
                  </div>
                ) : (
                  <span className="font-display text-4xl text-foreground">Custom</span>
                )}
              </div>

              <ul className="space-y-4 mb-10">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-3">
                    <Check className="w-4 h-4 text-foreground mt-0.5 shrink-0" />
                    <span className="text-sm text-muted-foreground">{feature}</span>
                  </li>
                ))}
              </ul>

              <a
                href="/login"
                className={`w-full py-4 flex items-center justify-center gap-2 text-sm font-medium transition-all group ${
                  plan.popular
                    ? "bg-foreground text-primary-foreground hover:bg-foreground/90"
                    : "border border-foreground/20 text-foreground hover:border-foreground hover:bg-foreground/5"
                }`}
              >
                {plan.cta}
                <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
              </a>
            </div>
          ))}
        </div>

        <p className="mt-12 text-center text-sm text-muted-foreground">
          All plans include automatic updates, HTTPS, and DDoS protection.{" "}
          <a href="#" className="underline underline-offset-4 hover:text-foreground transition-colors">
            Compare all features
          </a>
        </p>
        =========================================
        */}
      </div>
    </section>
  );
}
