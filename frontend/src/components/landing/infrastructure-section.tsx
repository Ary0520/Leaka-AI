"use client";

import { useEffect, useState, useRef } from "react";

const surfaces = [
  { name: "Private VPC", type: "Network", status: "Supported" },
  { name: "GitHub Actions", type: "Runner", status: "Supported" },
  { name: "Air-gapped / Ollama", type: "Inference", status: "Supported" },
  { name: "OpenRouter / Anthropic", type: "Cloud Inference", status: "Supported" },
];

export function InfrastructureSection() {
  const [isVisible, setIsVisible] = useState(false);
  const [activeSurface, setActiveSurface] = useState(0);
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setIsVisible(true);
      },
      { threshold: 0.1 }
    );

    if (sectionRef.current) observer.observe(sectionRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveSurface((prev) => (prev + 1) % surfaces.length);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <section ref={sectionRef} className="relative py-24 lg:py-32 overflow-hidden">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        <div className="grid lg:grid-cols-2 gap-16 lg:gap-24 items-center">
          {/* Left: Content */}
          <div
            className={`transition-all duration-700 ${
              isVisible ? "opacity-100 translate-x-0" : "opacity-0 -translate-x-8"
            }`}
          >
            <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground mb-6">
              <span className="w-8 h-px bg-foreground/30" />
              Infrastructure
            </span>
            <h2 className="text-4xl lg:text-6xl font-display tracking-tight mb-8">
              Your data plane.
              <br />
              Your walls.
            </h2>
            <p className="text-xl text-muted-foreground leading-relaxed mb-12">
              Leaka&apos;s control plane schedules jobs. A lightweight runner you deploy — inside your 
              GitHub Actions, your VPC, or fully air-gapped — executes them. Your DOM trees and staging 
              data never cross that line.
            </p>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-8">
              <div>
                <div className="text-4xl lg:text-5xl font-display mb-2">0</div>
                <div className="text-sm text-muted-foreground">Bytes of staging data sent to our cloud</div>
              </div>
              <div>
                <div className="text-4xl lg:text-5xl font-display mb-2">Self-hosted</div>
                <div className="text-sm text-muted-foreground">Runner deployment model</div>
              </div>
              <div>
                <div className="text-4xl lg:text-5xl font-display mb-2">Ollama</div>
                <div className="text-sm text-muted-foreground">Supported for offline inference</div>
              </div>
            </div>
          </div>

          {/* Right: Surfaces list */}
          <div
            className={`transition-all duration-700 delay-200 ${
              isVisible ? "opacity-100 translate-x-0" : "opacity-0 translate-x-8"
            }`}
          >
            <div className="border border-foreground/10">
              {/* Header */}
              <div className="px-6 py-4 border-b border-foreground/10 flex items-center justify-between">
                <span className="text-sm font-mono text-muted-foreground">Deployment Surfaces</span>
                <span className="flex items-center gap-2 text-xs font-mono text-green-600">
                  <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                  All operational
                </span>
              </div>

              {/* Surfaces */}
              <div>
                {surfaces.map((surface, index) => {
                  const isSupported = surface.status === "Supported";
                  return (
                    <div
                      key={surface.name}
                      className={`px-6 py-5 border-b border-foreground/5 last:border-b-0 flex items-center justify-between transition-all duration-300 ${
                        activeSurface === index ? "bg-foreground/[0.02]" : ""
                      }`}
                    >
                      <div className="flex items-center gap-4">
                        <span 
                          className={`w-2 h-2 rounded-full transition-colors duration-300 ${
                            isSupported 
                              ? (activeSurface === index ? "bg-foreground" : "bg-foreground/20")
                              : "bg-foreground/10"
                          }`}
                        />
                        <div>
                          <div className={`font-medium ${!isSupported && "text-muted-foreground"}`}>
                            {surface.name}
                          </div>
                          <div className="text-sm text-muted-foreground">{surface.type}</div>
                        </div>
                      </div>
                      <span className={`font-mono text-xs ${isSupported ? "text-green-600/70" : "text-muted-foreground/50"}`}>
                        {surface.status}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
