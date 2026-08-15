"use client";

import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/app/providers";

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
    accent: "rgba(87,241,219,0.05)",
    glow: "rgba(87,241,219,0.05)",
    title: "Write tests in plain English",
    body: "Describe a flow, and Leaka turns it into a real browser test without code. No brittle selectors or complex syntax.",
    offsetClass: "",
  },
  {
    id: "LKA-HLG-02",
    accent: "rgba(227,192,160,0.05)",
    glow: "rgba(227,192,160,0.05)",
    title: "Self-heal as UI changes",
    body: "Button moved, class changed, layout shifted — Leaka keeps going. Our agent understands intent, not just coordinates.",
    offsetClass: "-mt-8",
  },
  {
    id: "LKA-PRF-03",
    accent: "rgba(87,241,219,0.05)",
    glow: "rgba(87,241,219,0.05)",
    title: "Capture proof instantly",
    body: "On failure, get screenshots, steps taken, and a clean bug summary. Ready to be handed straight to engineering.",
    offsetClass: "mt-8",
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
          <span className="text-[#57f1db] text-base font-medium cursor-default">Home</span>
          <a
            href="#capabilities"
            className="text-[#bacac5] text-[11px] tracking-[1.65px] uppercase hover:text-[#e1e2e4] transition-colors"
            style={{ fontFamily: "serif" }}
          >
            Product
          </a>
          <a
            href="#how-it-works"
            className="text-[#bacac5] text-[11px] tracking-[1.65px] uppercase hover:text-[#e1e2e4] transition-colors"
            style={{ fontFamily: "serif" }}
          >
            Solutions
          </a>
          <a
            href="#integrations"
            className="text-[#bacac5] text-[11px] tracking-[1.65px] uppercase hover:text-[#e1e2e4] transition-colors"
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
        <section className="relative w-full min-h-[921px] flex items-center pt-20 pb-32 overflow-hidden" style={{ paddingTop: "160px" }}>
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
                  className="text-[64px] md:text-[72px] leading-[1.1] tracking-[-1.44px] text-[#e1e2e4]"
                  style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
                >
                  Autonomous QA for
                  <br />
                  revenue-critical
                  <br />
                  flows.
                </h1>
              </div>

              {/* Sub-copy */}
              <p className="text-[#bacac5] text-[18px] leading-[1.6] tracking-[0.18px] max-w-[520px] font-light mb-10">
                Leaka AI runs browser tests in plain English, self-heals when UI changes, and turns
                failures into screenshots, replayable steps, and auto-drafted tickets before broken
                flows cost you revenue.
              </p>

              {/* CTAs */}
              <div className="flex items-center gap-8 mb-10 flex-wrap">
                <Link href="/login">
                  <button
                    className="px-8 py-4 rounded-md text-[15px] font-semibold text-[#0B0E14] cursor-pointer transition-all hover:opacity-90 shadow-[0_4px_24px_rgba(87,241,219,0.25)] font-mono"
                    style={{ background: "#57f1db" }}
                  >
                    Test your first flow free
                  </button>
                </Link>
                <Link href="/dashboard">
                  <button
                    className="group px-2 py-4 text-[12px] tracking-[2px] uppercase text-[#57f1db] cursor-pointer transition-all hover:opacity-80 flex items-center gap-2 font-mono"
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
                className="text-[40px] md:text-[48px] leading-[1.2] text-[#e1e2e4]"
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
                  className="relative overflow-hidden flex items-center justify-between p-6 rounded-xl border border-white/5 bg-[#141718] group"
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
          id="capabilities"
          className="w-full py-32"
          style={{ background: "#111415" }}
        >
          <div className="max-w-[1440px] mx-auto px-6 flex flex-col gap-20">
            {/* Section header */}
            <div
              className="pb-6 flex flex-col gap-4"
              style={{ borderBottom: "1px solid rgba(186,202,197,0.05)" }}
            >
              <span
                className="text-[#57f1db] text-[11px] tracking-[2.2px] uppercase"
                style={{ fontFamily: "Georgia, serif" }}
              >
                02 / CAPABILITIES
              </span>
              <h2
                className="text-[40px] leading-[1.5] text-[#e1e2e4]"
                style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
              >
                What Leaka does
              </h2>
            </div>

            {/* Cards */}
            <div className="flex flex-col md:flex-row items-start gap-12 justify-center">
              {CAPABILITY_CARDS.map((card) => (
                <div
                  key={card.id}
                  className={`relative flex flex-col gap-4 p-8 rounded-2xl overflow-hidden flex-1 ${card.offsetClass}`}
                  style={{
                    background: "rgba(29,32,33,0.2)",
                    border: "1px solid rgba(225,226,228,0.05)",
                    backdropFilter: "blur(10px)",
                  }}
                >
                  {/* Corner glow */}
                  <div
                    className="absolute rounded-xl size-48 -top-24 -left-24 blur-[32px] pointer-events-none"
                    style={{ background: card.glow }}
                  />
                  <span
                    className="text-[#bacac5] text-[10px] tracking-[1px] uppercase opacity-50"
                    style={{ fontFamily: "Georgia, serif" }}
                  >
                    {card.id}
                  </span>
                  <h3
                    className="text-[#e1e2e4] text-[24px] leading-[32px] mt-8"
                    style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
                  >
                    {card.title}
                  </h3>
                  <p className="text-[#bacac5] text-[16px] leading-[24px]">{card.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── HOW IT WORKS ─────────────────────────────────────────────────── */}
        <section
          id="how-it-works"
          className="w-full py-32 px-6"
          style={{ background: "#111415" }}
        >
          <div className="max-w-[1440px] mx-auto grid grid-cols-12 gap-20">
            {/* Left copy */}
            <div className="col-span-12 md:col-span-4 flex flex-col justify-center py-16">
              <div className="mb-4">
                <span
                  className="text-[#e3c0a0] text-[11px] tracking-[2.2px] uppercase"
                  style={{ fontFamily: "Georgia, serif" }}
                >
                  03 / EXECUTION
                </span>
              </div>
              <h2
                className="text-[40px] leading-[1.5] text-[#e1e2e4] mb-6"
                style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
              >
                How it works
              </h2>
              <p className="text-[#bacac5] text-[16px] leading-[24px]">
                A streamlined pipeline from human intent to robust verification, designed to run
                autonomously in the background.
              </p>
            </div>

            {/* Right steps */}
            <div className="col-span-12 md:col-span-8 relative flex flex-col">
              {/* Vertical timeline line */}
              <div
                className="absolute left-8 top-0 bottom-0 w-px"
                style={{
                  background:
                    "linear-gradient(to bottom, rgba(87,241,219,0.0) 0%, rgba(87,241,219,0.3) 20%, rgba(87,241,219,0.3) 80%, rgba(87,241,219,0) 100%)",
                }}
              />

              <div className="flex flex-col gap-16 pl-24">
                {STEPS.map((step, i) => (
                  <div key={i} className="relative flex flex-col gap-2">
                    {/* Timeline dot */}
                    <div
                      className="absolute -left-16 top-1 size-2 rounded-sm"
                      style={{
                        background: "#111415",
                        border: "1px solid #57f1db",
                        boxShadow: "0px 0px 10px 0px rgba(45,212,191,0.5)",
                      }}
                    />
                    <span
                      className="text-[#57f1db] text-[12px] tracking-[1.2px]"
                      style={{ fontFamily: "Georgia, serif" }}
                    >
                      {step.label}
                    </span>
                    <h4
                      className="text-[#e1e2e4] text-[20px] leading-[28px]"
                      style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
                    >
                      {step.title}
                    </h4>
                    <p className="text-[#bacac5] text-[16px] leading-[24px]">{step.body}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ── INTEGRATIONS ─────────────────────────────────────────────────── */}
        <section
          id="integrations"
          className="w-full py-24"
          style={{ background: "#111415" }}
        >
          <div className="max-w-[1440px] mx-auto px-6 flex flex-col gap-8">
            <div className="flex justify-center">
              <span
                className="text-[#3c4a46] text-[11px] tracking-[2.2px] uppercase text-center"
                style={{ fontFamily: "Georgia, serif" }}
              >
                04 / INTEGRATIONS
              </span>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-4">
              {INTEGRATIONS.map((name) => (
                <div
                  key={name}
                  className="px-6 py-3 rounded-xl text-[14px] text-[#bacac5] text-center"
                  style={{
                    background: "rgba(40,42,44,0.3)",
                    border: "1px solid rgba(186,202,197,0.1)",
                    backdropFilter: "blur(6px)",
                    fontFamily: "Georgia, serif",
                  }}
                >
                  {name}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── CTA ──────────────────────────────────────────────────────────── */}
        <section
          className="relative w-full py-48 overflow-hidden"
          style={{ background: "#111415" }}
        >
          {/* Decorative concentric borders */}
          <div className="absolute inset-0 pointer-events-none opacity-10">
            <div
              className="absolute rounded-xl"
              style={{
                width: 800,
                height: 800,
                left: "calc(50% - 400px)",
                top: -75,
                border: "1px solid rgba(87,241,219,0.2)",
              }}
            />
            <div
              className="absolute rounded-xl"
              style={{
                width: 600,
                height: 600,
                left: "calc(50% - 300px)",
                top: 25,
                border: "1px solid rgba(87,241,219,0.3)",
              }}
            />
            <div
              className="absolute rounded-xl"
              style={{
                width: 400,
                height: 400,
                left: "calc(50% - 200px)",
                top: 125,
                border: "1px solid rgba(87,241,219,0.4)",
              }}
            />
          </div>

          <div className="relative z-10 flex flex-col items-center gap-12 max-w-3xl mx-auto px-6 text-center">
            <h2
              className="text-[48px] md:text-[64px] leading-[1.25] text-[#e1e2e4]"
              style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
            >
              Stop broken flows before
              <br />
              they cost you money.
            </h2>
            <Link href="/login">
              <button
                className="px-12 py-5 rounded-xl text-[14px] tracking-[2.8px] uppercase font-bold text-[#57f1db] transition-all hover:shadow-[0_0_40px_rgba(45,212,191,0.2)] cursor-pointer"
                style={{
                  fontFamily: "Georgia, serif",
                  background: "rgba(87,241,219,0.1)",
                  border: "1px solid rgba(87,241,219,0.3)",
                  boxShadow: "0px 0px 30px 0px rgba(45,212,191,0.1)",
                }}
              >
                BOOK A DEMO
              </button>
            </Link>
          </div>
        </section>
      </main>

      {/* ── FOOTER ─────────────────────────────────────────────────────────── */}
      <footer
        className="border-t opacity-20"
        style={{ borderColor: "rgba(186,202,197,0.05)" }}
      >
        <div className="max-w-[1440px] mx-auto px-6 pt-12 pb-8 flex items-center justify-between">
          <span
            className="text-[#bacac5] text-[11px] tracking-[1.65px]"
            style={{ fontFamily: "Georgia, serif" }}
          >
            © 2024 Leaka Research
          </span>
          <div className="flex items-center gap-12">
            <span
              className="text-[#bacac5] text-[11px] tracking-[1.65px]"
              style={{ fontFamily: "Georgia, serif" }}
            >
              Orbital Status: Nominal
            </span>
            <Link
              href="/dashboard"
              className="text-[#bacac5] text-[11px] tracking-[1.65px] hover:text-[#e1e2e4] transition-colors"
              style={{ fontFamily: "Georgia, serif" }}
            >
              Terminal Protocols
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
