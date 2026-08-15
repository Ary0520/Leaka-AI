"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/app/providers";
import { Keyboard, Activity, Camera } from "lucide-react";
import { LivePreview } from "@/components/live-preview";
import { IntegrationsCarousel } from "@/components/integrations-carousel";

// ─── Figma asset: nav arrow ───────────────────────────────────────────────────
const NAV_ARROW = "/figma-assets/leaka-nav-arrow.svg";

// ─── Steps data ───────────────────────────────────────────────────────────────
const STEPS = [
  {
    label: "STEP 01",
    title: "Describe the flow",
    body: `Input your test scenario in natural language. "Go to pricing, select Pro plan, fill out checkout with dummy data, verify success page."`,
  },
  {
    label: "STEP 02",
    title: "Asynchronous Execution",
    body: "Leaka spins up a secure browser instance, interpreting the steps and navigating the UI just like a human user would, adapting to minor changes.",
  },
  {
    label: "STEP 03",
    title: "Analysis & Output",
    body: "Receive a detailed report. If the test fails, Leaka provides a step-by-step trace, visual evidence, and a pre-drafted ticket detailing exactly what broke.",
  },
];

const CAPABILITY_CARDS = [
  {
    id: "LKA-TXT-01",
    title: "Write tests in plain English.",
    body: "No coding required. Just tell Leaka what to do: \"Go to pricing, click Pro, fill checkout, and verify success.\" It translates English into resilient automation.",
    icon: Keyboard,
  },
  {
    id: "LKA-HLG-02",
    title: "Self-heals when your UI changes.",
    body: "Moved a button? Changed an ID? Leaka uses computer vision to understand the page like a human, so tests don't break just because your CSS updated.",
    icon: Activity,
  },
  {
    id: "LKA-PRF-03",
    title: "Proof, not just a red X.",
    body: "Receive a detailed report. If the test fails, Leaka provides a step-by-step trace, error-screenshot, and creates ticket detailing exactly what broke.",
    icon: Camera,
  },
];

const INTEGRATIONS = ["Linear", "Jira", "GitHub Actions", "Slack", "Resend"];

const FEATURE_TAGS = [
  "NATURAL LANGUAGE TESTS",
  "SELF-HEALING EXECUTION",
  "VISUAL PROOF ON FAILURE",
  "AUTO-TICKETING",
];

// ─── Component ────────────────────────────────────────────────────────────────
export default function LandingPage() {
  const { user, loading } = useAuth();
  const [activeSection, setActiveSection] = useState("home");

  useEffect(() => {
    const handleScroll = () => {
      const sections = ["home", "how-it-works", "see-it-live", "pricing"];
      let currentSection = "home";

      for (const section of sections) {
        const el = document.getElementById(section);
        if (el) {
          const rect = el.getBoundingClientRect();
          if (rect.top <= window.innerHeight / 2) {
            currentSection = section;
          }
        }
      }
      setActiveSection(currentSection);
    };

    window.addEventListener("scroll", handleScroll);
    handleScroll(); // Initial check
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div
      className="min-h-screen w-full text-[#e1e2e4] overflow-x-hidden"
      style={{ background: "#111415" }}
    >
      {/* ── HEADER ─────────────────────────────────────────────────────────── */}
      <header className="fixed top-0 left-0 right-0 z-50 flex h-20 items-center justify-between px-6 max-w-[1440px] mx-auto">
        {/* Logo */}
        <div className="flex items-center">
          <Image
            src="/leaka-logo.png"
            alt="Leaka AI"
            width={80}
            height={40}
            className="object-contain"
            priority
          />
        </div>

        {/* Nav pill */}
        <nav
          className="hidden md:flex items-center gap-12 px-12 py-3 rounded-xl"
          style={{
            background: "rgba(29,32,33,0.2)",
            border: "1px solid rgba(186,202,197,0.05)",
            backdropFilter: "blur(6px)",
          }}
        >
          <a
            href="#home"
            className={`${activeSection === 'home' ? 'text-[#57f1db] drop-shadow-[0_0_8px_rgba(87,241,219,0.8)] font-bold' : 'text-[#bacac5] hover:text-[#e1e2e4]'} text-[11px] tracking-[1.65px] uppercase transition-all duration-300`}
            style={{ fontFamily: "serif" }}
          >
            Home
          </a>
          <a
            href="#how-it-works"
            className={`${activeSection === 'how-it-works' ? 'text-[#57f1db] drop-shadow-[0_0_8px_rgba(87,241,219,0.8)] font-bold' : 'text-[#bacac5] hover:text-[#e1e2e4]'} text-[11px] tracking-[1.65px] uppercase transition-all duration-300`}
            style={{ fontFamily: "serif" }}
          >
            Product
          </a>
          <a
            href="#see-it-live"
            className={`${activeSection === 'see-it-live' ? 'text-[#57f1db] drop-shadow-[0_0_8px_rgba(87,241,219,0.8)] font-bold' : 'text-[#bacac5] hover:text-[#e1e2e4]'} text-[11px] tracking-[1.65px] uppercase transition-all duration-300`}
            style={{ fontFamily: "serif" }}
          >
            Demo
          </a>
          <a
            href="#pricing"
            className={`${activeSection === 'pricing' ? 'text-[#57f1db] drop-shadow-[0_0_8px_rgba(87,241,219,0.8)] font-bold' : 'text-[#bacac5] hover:text-[#e1e2e4]'} text-[11px] tracking-[1.65px] uppercase transition-all duration-300`}
            style={{ fontFamily: "serif" }}
          >
            Pricing
          </a>
        </nav>

        {/* CTA icon button */}
        <div className="flex items-center">
          {!loading && (
            user ? (
              <Link href="/dashboard">
                <div
                  className="flex items-center justify-center rounded-xl size-8 shrink-0 cursor-pointer transition-all hover:shadow-[0_0_15px_rgba(87,241,219,0.5)]"
                  style={{
                    background: "#57f1db",
                    boxShadow: "0px 0px 7.5px rgba(87,241,219,0.3)",
                  }}
                >
                  <Image src={NAV_ARROW} alt="Dashboard" width={12} height={12} />
                </div>
              </Link>
            ) : (
              <Link href="/login">
                <button
                  className="px-4 py-2 rounded-md text-[14px] font-semibold text-[#0B0E14] cursor-pointer transition-all hover:opacity-90 shadow-sm font-mono"
                  style={{ background: "#57f1db" }}
                >
                  Start free
                </button>
              </Link>
            )
          )}
        </div>
      </header>

      {/* ── MAIN ───────────────────────────────────────────────────────────── */}
      <main>

        {/* ── HERO ─────────────────────────────────────────────────────────── */}
        <section id="home" className="relative w-full min-h-[921px] flex items-center pt-20 pb-32 overflow-hidden" style={{ paddingTop: "160px" }}>
          {/* Ambient glow layer */}
          <div
            className="absolute inset-0 mix-blend-screen opacity-20 pointer-events-none"
            style={{
              backgroundImage: `
                radial-gradient(ellipse 510px 510px at 70% 30%, rgba(45,212,191,0.15) 0%, rgba(45,212,191,0) 60%),
                radial-gradient(ellipse 510px 510px at 30% 70%, rgba(255,218,185,0.05) 0%, rgba(255,218,185,0) 60%)
              `,
            }}
          />

          {/* ─ Hero video slot (replaces Figma dashboard image) ─ */}
          <div className="absolute inset-0 pointer-events-none">
            {/* Left-to-right fade overlay so text stays readable */}
            <div
              className="absolute inset-0 z-10"
              style={{
                background:
                  "linear-gradient(90deg, #111415 0%, rgba(17,20,21,0.6) 35%, rgba(17,20,21,0) 70%)",
              }}
            />
            {/* Bottom fade */}
            <div
              className="absolute inset-0 z-10"
              style={{
                background:
                  "linear-gradient(to top, #111415 0%, rgba(17,20,21,0) 30%)",
              }}
            />
            {/* VIDEO — positioned so the top portion of the clip is visible */}
            <video
              className="absolute w-full h-full object-cover opacity-100"
              style={{ top: "-17%", left: 15, objectPosition: "center top" }}
              // src="/hero-section-video.mp4"
              // src="/liquidDropAnimation.mp4"
              // src="/leaka ai new vid hero.mp4"
              src="/oildropVid.mp4"
              autoPlay
              muted
              loop
              playsInline
            />
          </div>

          {/* Hero content */}
          <div className="relative z-20 max-w-[1440px] mx-auto px-6 grid grid-cols-12 gap-6 w-full items-center">
            <div className="col-span-12 md:col-span-6 flex flex-col items-start justify-end gap-0">
              {/* Heading */}
              <div className="mb-6">
                <h1
                  className="text-[42px] sm:text-[56px] md:text-[64px] lg:text-[72px] leading-[1.1] tracking-[-1.44px] text-[#e1e2e4] break-words"
                  style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
                >
                  Autonomous QA for
                  <br className="hidden sm:block" />
                  <span className="sm:hidden"> </span>revenue-critical
                  <br className="hidden sm:block" />
                  <span className="sm:hidden"> </span>flows.
                </h1>
              </div>

              {/* Sub-copy (Desktop) */}
              <p className="hidden md:block text-[#bacac5] text-[18px] leading-[1.6] tracking-[0.18px] max-w-[520px] font-light mb-10">
                Leaka AI runs browser tests in plain English, self-heals when UI changes, and turns
                failures into screenshots, replayable steps, and auto-drafted tickets before broken
                flows cost you revenue.
              </p>

              {/* Sub-copy (Mobile) */}
              <p className="md:hidden text-[#bacac5] text-[16px] sm:text-[18px] leading-[1.6] tracking-[0.18px] font-light mb-8">
                Run tests in plain English. Leaka self-heals as your UI changes, catching broken flows before they cost you revenue.
              </p>

              {/* CTAs */}
              <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6 sm:gap-8 mb-10 w-full sm:w-auto">
                <Link href="/login" className="w-full sm:w-auto">
                  <button
                    className="w-full sm:w-auto px-8 py-4 rounded-md text-[15px] font-semibold text-[#0B0E14] cursor-pointer transition-all hover:opacity-90 shadow-[0_4px_24px_rgba(87,241,219,0.25)] font-mono text-center justify-center"
                    style={{ background: "#57f1db" }}
                  >
                    Test your first flow free
                  </button>
                </Link>
                <Link href="#see-it-live" className="w-full sm:w-auto">
                  <button
                    className="w-full sm:w-auto group px-2 py-4 text-[12px] tracking-[2px] uppercase text-[#57f1db] cursor-pointer transition-all hover:opacity-80 flex items-center justify-start sm:justify-center gap-2 font-mono"
                  >
                    WATCH IT CATCH A BUG <span className="group-hover:translate-y-1 transition-transform">↓</span>
                  </button>
                </Link>
              </div>


            </div>
          </div>
        </section>

        {/* ── THE PROBLEM ──────────────────────────────────────────────────── */}
        <section
          id="the-problem"
          className="w-full pt-8 pb-32 relative z-30"
          style={{ background: "#111415" }}
        >
          <div className="max-w-[1440px] mx-auto px-6 grid grid-cols-12 gap-16 md:gap-24 items-center">
            {/* Left side */}
            <div className="col-span-12 md:col-span-6 flex flex-col items-start gap-8">
              <div className="flex items-center gap-6 w-full">
                <span
                  className="text-[#57f1db] text-[11px] tracking-[2.2px] uppercase font-mono"
                >
                  01 / THE PROBLEM
                </span>
                <div className="flex-1 h-px bg-white/5"></div>
              </div>
              <h2
                className="text-[32px] sm:text-[40px] md:text-[48px] leading-[1.2] text-[#e1e2e4] break-words"
                style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
              >
                Stop writing browser instructions at 2 am.
              </h2>
              <p className="text-[#bacac5] text-[14px] md:text-[15px] leading-[1.8] font-mono opacity-80 max-w-[500px]">
                Traditional test scripts force you to manage the DOM manually. Your tests break when the UI changes.
                 <br />
                Leaka adapts to the changes automatically, trigger alerts, and saves you revenue before a customer complains.
              </p>
            </div>

            {/* Right side */}
            <div className="col-span-12 md:col-span-6 flex flex-col gap-4">
              {[
                { flow: "E-COMMERCE_CHECKOUT", issue: "Promo code field silently rejecting valid input" },
                { flow: "SAAS_ONBOARDING", issue: "Signup flow hangs after email verification" },
                { flow: "PLAN_UPGRADE", issue: "Upgrade button firing the wrong plan" },
              ].map((item, i) => (
                <div
                  key={i}
                  className="relative overflow-hidden flex flex-col md:flex-row items-start md:items-center justify-between p-6 rounded-xl border border-white/5 bg-[#141718] group gap-4 md:gap-0"
                >
                  {/* Subtle animated background gradient on hover */}
                  <div 
                    className="absolute inset-0 opacity-0 group-hover:opacity-10 transition-opacity duration-700 pointer-events-none" 
                    style={{ background: 'linear-gradient(90deg, transparent, rgba(87,241,219,0.3), transparent)' }}
                  />
                  
                  <span 
                    className="animate-text-shimmer text-[12px] font-mono uppercase tracking-[1.5px] font-bold relative z-10"
                    style={{ animationDelay: `${i * 1}s` }}
                  >
                    {item.flow}
                  </span>
                  
                  <div className="flex items-center gap-3 text-[#bacac5] opacity-80 relative z-10">
                    <svg 
                      className="w-4 h-4 text-[#e3c0a0] animate-pulse-amber" 
                      style={{ animationDelay: `${i * 1}s` }}
                      fill="none" stroke="currentColor" viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                    </svg>
                    <span className="text-[11px] font-mono tracking-wide">{item.issue}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── CAPABILITIES ─────────────────────────────────────────────────── */}
        <section
          id="how-it-works"
          className="w-full py-32"
          style={{ background: "#111415" }}
        >
          <div className="max-w-[1440px] mx-auto px-6 flex flex-col gap-12">
            {/* Section header */}
            <div className="flex items-center gap-6 w-full">
              <span
                className="text-[#57f1db] text-[11px] tracking-[2.2px] uppercase font-mono"
              >
                02 / HOW IT WORKS
              </span>
              <div className="flex-1 h-px bg-white/5"></div>
            </div>

            {/* Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {CAPABILITY_CARDS.map((card, i) => {
                const Icon = card.icon;
                return (
                  <div
                    key={card.id}
                    className="group relative p-[1px] rounded-2xl overflow-hidden flex flex-col"
                  >
                    {/* The scanning border background */}
                    <div className="absolute inset-0 bg-white/5 z-0" />
                    <div 
                      className="absolute inset-[-100%] animate-[spin_5s_linear_infinite] opacity-40 group-hover:opacity-100 transition-opacity duration-700 z-0"
                      style={{ 
                        background: 'conic-gradient(from 90deg at 50% 50%, transparent 0%, transparent 75%, rgba(87,241,219,0.6) 100%)', 
                        animationDelay: `${i * 1.5}s` 
                      }} 
                    />
                    
                    {/* The inner card content */}
                    <div className="relative z-10 flex flex-col h-full bg-[#141718] rounded-[15px] p-8">
                      {/* Hover Animated Inner Glow */}
                      <div 
                        className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" 
                        style={{ background: 'radial-gradient(circle at top right, rgba(87,241,219,0.03), transparent 70%)' }}
                      />
                      
                      {/* Top Row: Icon + Badge */}
                      <div className="flex justify-between items-start mb-12 relative z-10">
                        <div className="flex items-center justify-center size-10 rounded-xl border border-white/5 bg-white/[0.02] group-hover:border-white/20 transition-colors">
                          <Icon className="w-5 h-5 text-[#bacac5] group-hover:text-white transition-colors" />
                        </div>
                        <span className="text-[#bacac5] text-[10px] font-mono tracking-[1.5px] uppercase opacity-70">
                          {card.id}
                        </span>
                      </div>

                      <h3
                        className="text-[#e1e2e4] text-[26px] leading-[1.3] mb-6 relative z-10"
                        style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
                      >
                        {card.title}
                      </h3>
                      <p className="text-[#bacac5] text-[13px] leading-[1.8] font-mono opacity-80 relative z-10">
                        {card.body}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* ── SEE IT LIVE ──────────────────────────────────────────────────── */}
        <div id="see-it-live">
          <LivePreview />
        </div>

        {/* ── INTEGRATIONS CAROUSEL ─────────────────────────────────────────────────── */}
        <IntegrationsCarousel />

        {/* ── CTA ──────────────────────────────────────────────────────────── */}
        <section
          id="pricing"
          className="relative w-full py-32 overflow-hidden border-t border-white/5"
          style={{ background: "#111415" }}
        >
          {/* Subtle noise/texture background & glow */}
          <div className="absolute inset-0 pointer-events-none opacity-20" style={{ background: "url('data:image/svg+xml;utf8,%3Csvg viewBox=%220 0 200 200%22 xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cfilter id=%22noiseFilter%22%3E%3CfeTurbulence type=%22fractalNoise%22 baseFrequency=%220.65%22 numOctaves=%223%22 stitchTiles=%22stitch%22/%3E%3C/filter%3E%3Crect width=%22100%25%22 height=%22100%25%22 filter=%22url(%23noiseFilter)%22/%3E%3C/svg%3E')" }} />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] bg-[#57f1db]/10 blur-[120px] pointer-events-none rounded-full" />

          <div className="relative z-10 flex flex-col items-center gap-10 max-w-3xl mx-auto px-6 text-center">
            <div className="mb-2">
              {/* <span
                className="text-[#e3c0a0] text-[11px] tracking-[2.2px] uppercase bg-[#e3c0a0]/10 px-4 py-2 rounded-full font-mono border border-[#e3c0a0]/20"
              >
                06 / GET STARTED
              </span> */}
            </div>
            
            <h2
              className="text-[48px] md:text-[64px] leading-[1.1] text-[#e1e2e4] tracking-tight"
              style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
            >
              Stop broken flows before
              <br />
              they cost you money.
            </h2>
            
            <p className="text-[#bacac5] text-[18px] leading-[1.6] max-w-[500px]">
              Join leading engineering teams automating their browser tests. Setup takes exactly 2 minutes.
            </p>

            <Link href="/login" className="mt-4">
              <button
                className="group px-8 py-4 rounded-xl text-[14px] uppercase font-bold text-[#0B0E14] transition-all hover:opacity-90 flex items-center gap-3 cursor-pointer"
                style={{
                  background: "#57f1db",
                  boxShadow: "0px 4px 30px rgba(87,241,219,0.3), inset 0px 1px 1px rgba(255,255,255,0.4)",
                  fontFamily: "Georgia, serif",
                }}
              >
                BOOK A DEMO
                <svg className="w-4 h-4 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
              </button>
            </Link>
          </div>
        </section>
      </main>

      {/* ── FAT FOOTER ─────────────────────────────────────────────────────────── */}
      <footer
        className="w-full relative z-10 border-t"
        style={{ background: "#0B0E14", borderColor: "rgba(186,202,197,0.05)" }}
      >
        <div className="max-w-[1440px] mx-auto px-6 pt-24 pb-12 flex flex-col gap-16">
          {/* Top Grid */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-12 md:gap-8">
            
            {/* Left Col: Brand */}
            <div className="col-span-1 md:col-span-4 flex flex-col gap-6 pr-8">
              <div className="flex items-center gap-1">
                <Image src="/leaka-logo.png" alt="Leaka" width={40} height={40} className="opacity-90" />
                <span className="text-[#e1e2e4] font-bold text-[20px] tracking-tight" style={{ fontFamily: "Georgia, serif" }}>Leaka AI</span>
              </div>
              <p className="text-[#bacac5] text-[14px] leading-[1.8] opacity-70">
                Self-healing browser tests that understand plain English. Built for modern engineering teams who value robust verification over fragile scripts.
              </p>
            </div>

            {/* Link Columns */}
            <div className="col-span-1 md:col-span-8 grid grid-cols-2 md:grid-cols-3 gap-12">
              <div className="flex flex-col gap-5">
                <span className="text-[#57f1db] text-[11px] tracking-[2px] uppercase font-mono">Product</span>
                <Link href="#" className="text-[#bacac5] hover:text-white transition-colors text-[14px]">Features</Link>
                <Link href="#" className="text-[#bacac5] hover:text-white transition-colors text-[14px]">Integrations</Link>
                <Link href="#" className="text-[#bacac5] hover:text-white transition-colors text-[14px]">Pricing</Link>
                <Link href="#" className="text-[#bacac5] hover:text-white transition-colors text-[14px]">Changelog</Link>
              </div>
              <div className="flex flex-col gap-5">
                <span className="text-[#57f1db] text-[11px] tracking-[2px] uppercase font-mono">Resources</span>
                <Link href="#" className="text-[#bacac5] hover:text-white transition-colors text-[14px]">Documentation</Link>
                <Link href="#" className="text-[#bacac5] hover:text-white transition-colors text-[14px]">Blog</Link>
                <Link href="#" className="text-[#bacac5] hover:text-white transition-colors text-[14px]">Support</Link>
                <Link href="#" className="text-[#bacac5] hover:text-white transition-colors text-[14px] flex items-center gap-2">
                  System Status
                  <span className="size-1.5 bg-[#57f1db] rounded-full animate-pulse shadow-[0_0_8px_rgba(87,241,219,0.8)]" />
                </Link>
              </div>
              <div className="flex flex-col gap-5">
                <span className="text-[#57f1db] text-[11px] tracking-[2px] uppercase font-mono">Company</span>
                <Link href="#" className="text-[#bacac5] hover:text-white transition-colors text-[14px]">About</Link>
                <Link href="#" className="text-[#bacac5] hover:text-white transition-colors text-[14px]">Careers</Link>
                <Link href="#" className="text-[#bacac5] hover:text-white transition-colors text-[14px]">Contact</Link>
                <Link href="#" className="text-[#bacac5] hover:text-white transition-colors text-[14px]">Twitter / X</Link>
              </div>
            </div>
          </div>

          {/* Bottom Bar */}
          <div className="border-t border-white/5 pt-8 flex flex-col md:flex-row items-center justify-between gap-4">
            <span
              className="text-[#bacac5] text-[12px] opacity-50"
            >
              © 2026 Leaka Research Inc. All rights reserved.
            </span>
            <div className="flex items-center gap-6">
              <Link href="#" className="text-[#bacac5] opacity-50 hover:opacity-100 transition-opacity text-[12px]">Terms of Service</Link>
              <Link href="#" className="text-[#bacac5] opacity-50 hover:opacity-100 transition-opacity text-[12px]">Privacy Policy</Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
