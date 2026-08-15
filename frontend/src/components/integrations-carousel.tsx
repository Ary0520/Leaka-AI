"use client";

import React from "react";

export function IntegrationsCarousel() {
  return (
    <section
      id="integrations"
      className="w-full py-32 px-6 overflow-hidden relative"
      style={{ background: "#111415" }}
    >
      {/* Subtle background glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[300px] bg-[#57f1db]/5 blur-[120px] pointer-events-none" />
      
      <div className="max-w-[1440px] mx-auto flex flex-col items-center justify-center relative z-10">
        <div className="mb-6">
          <span
            className="text-[#e3c0a0] text-[11px] tracking-[2.2px] uppercase text-center block"
            style={{ fontFamily: "Georgia, serif" }}
          >
            04 / INTEGRATIONS
          </span>
        </div>
        <h2
          className="text-[40px] md:text-[48px] leading-[1.2] text-[#e1e2e4] text-center mb-16"
          style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
        >
          Leaka connects with your stack.
        </h2>
        
        {/* Infinite Marquee */}
        <div className="w-full max-w-[1200px] relative overflow-hidden">
          {/* Fade masks */}
          <div className="absolute left-0 top-0 bottom-0 w-32 bg-gradient-to-r from-[#111415] to-transparent z-10" />
          <div className="absolute right-0 top-0 bottom-0 w-32 bg-gradient-to-l from-[#111415] to-transparent z-10" />
          
          <div className="flex w-max animate-marquee">
            {/* Two sets for perfect infinite loop */}
            {[...Array(2)].map((_, i) => (
              <div key={i} className="flex shrink-0 items-center gap-24 pr-24">
                <LogoSlack />
                <LogoLinear />
                <LogoJira />
                <LogoGithub />
                <LogoResend />
                <LogoOpenAI />
                <LogoClaude />
                <LogoOpenRouter />
                <LogoOllama />
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

// Logo SVG Components

const LogoSlack = () => (
  <div className="flex items-center gap-3 text-[#bacac5] opacity-50 hover:opacity-100 hover:text-white hover:drop-shadow-[0_0_10px_rgba(255,255,255,0.5)] transition-all duration-300 cursor-default">
    <svg className="h-8" viewBox="0 0 122.8 122.8" fill="currentColor">
      <path d="M25.8 77.6c0 7.1-5.8 12.9-12.9 12.9S0 84.7 0 77.6s5.8-12.9 12.9-12.9h12.9v12.9zm6.5 0c0-7.1 5.8-12.9 12.9-12.9s12.9 5.8 12.9 12.9v32.3c0 7.1-5.8 12.9-12.9 12.9s-12.9-5.8-12.9-12.9V77.6z"/>
      <path d="M45.2 25.8c-7.1 0-12.9-5.8-12.9-12.9S38.1 0 45.2 0s12.9 5.8 12.9 12.9v12.9H45.2zm0 6.5c7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9H12.9C5.8 58.1 0 52.3 0 45.2s5.8-12.9 12.9-12.9h32.3z"/>
      <path d="M97 45.2c0-7.1 5.8-12.9 12.9-12.9s12.9 5.8 12.9 12.9-5.8 12.9-12.9 12.9H97V45.2zm-6.5 0c0 7.1-5.8 12.9-12.9 12.9s-12.9-5.8-12.9-12.9V12.9C64.7 5.8 70.5 0 77.6 0s12.9 5.8 12.9 12.9v32.3z"/>
      <path d="M77.6 97c7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9-12.9-5.8-12.9-12.9V97h12.9zm0-6.5c-7.1 0-12.9-5.8-12.9-12.9s5.8-12.9 12.9-12.9h32.3c7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9H77.6z"/>
    </svg>
    <span className="font-bold text-2xl tracking-tight font-sans">Slack</span>
  </div>
);

const LogoLinear = () => (
  <div className="flex items-center gap-3 opacity-50 hover:opacity-100 hover:drop-shadow-[0_0_10px_rgba(255,255,255,0.5)] transition-all duration-300 cursor-default">
    <img src="/linearLogo.svg" alt="Linear" className="h-8" />
  </div>
);

const LogoJira = () => (
  <div className="flex items-center gap-3 opacity-50 hover:opacity-100 hover:drop-shadow-[0_0_10px_rgba(255,255,255,0.5)] transition-all duration-300 cursor-default">
    <img src="/jiraLogo.svg" alt="Jira" className="h-8" />
  </div>
);

const LogoGithub = () => (
  <div className="flex items-center gap-3 text-[#bacac5] opacity-50 hover:opacity-100 hover:text-white hover:drop-shadow-[0_0_10px_rgba(255,255,255,0.5)] transition-all duration-300 cursor-default">
    <svg className="h-8" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.295 24 12c0-6.63-5.37-12-12-12" />
    </svg>
    <span className="font-bold text-2xl tracking-tighter font-sans">GitHub</span>
  </div>
);

const LogoResend = () => (
  <div className="flex items-center gap-3 opacity-50 hover:opacity-100 hover:drop-shadow-[0_0_10px_rgba(255,255,255,0.5)] transition-all duration-300 cursor-default">
    <img src="https://cdn.resend.com/brand/resend-wordmark-white.svg" alt="Resend" className="h-8" />
  </div>
);

const LogoOpenAI = () => (
  <div className="flex items-center gap-3 opacity-50 hover:opacity-100 hover:drop-shadow-[0_0_10px_rgba(255,255,255,0.5)] transition-all duration-300 cursor-default text-[#bacac5] hover:text-white">
    <img src="/openai.svg" alt="OpenAI" className="h-8" />
    <span className="font-bold text-2xl tracking-tight font-sans">OpenAI</span>
  </div>
);

const LogoClaude = () => (
  <div className="flex items-center gap-3 opacity-50 hover:opacity-100 hover:drop-shadow-[0_0_10px_rgba(255,255,255,0.5)] transition-all duration-300 cursor-default text-[#bacac5] hover:text-white">
    <img src="/claude.svg" alt="Claude" className="h-8" />
    <span className="font-medium text-3xl tracking-tight" style={{ fontFamily: "Georgia, serif" }}>Claude</span>
  </div>
);

const LogoOpenRouter = () => (
  <div className="flex items-center gap-3 opacity-50 hover:opacity-100 hover:drop-shadow-[0_0_10px_rgba(255,255,255,0.5)] transition-all duration-300 cursor-default text-[#bacac5] hover:text-white">
    <img src="/openrouter.svg" alt="OpenRouter" className="h-8" />
    <span className="font-bold text-2xl tracking-tight font-sans">OpenRouter</span>
  </div>
);

const LogoOllama = () => (
  <div className="flex items-center gap-3 opacity-50 hover:opacity-100 hover:drop-shadow-[0_0_10px_rgba(255,255,255,0.5)] transition-all duration-300 cursor-default text-[#bacac5] hover:text-white">
    <img src="/ollama.svg" alt="Ollama" className="h-8" />
    <span className="font-bold text-2xl tracking-tight font-sans">Ollama</span>
  </div>
);
