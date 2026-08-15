"use client";

import React, { useState, useEffect } from "react";
import { Check, AlertCircle, XCircle } from "lucide-react";

export function LivePreview() {
  const [step, setStep] = useState(0);
  const [typedText, setTypedText] = useState("");

  useEffect(() => {
    let timeout: NodeJS.Timeout;

    if (step === 0) {
      // Step 0: Load initial browser
      timeout = setTimeout(() => setStep(1), 1200);
    } else if (step === 1) {
      // Step 1: Render form
      timeout = setTimeout(() => setStep(2), 800);
    } else if (step === 2) {
      // Step 2: Type "WINTER24"
      const textToType = "WINTER24";
      let currentIndex = 0;
      
      const typeNextChar = () => {
        if (currentIndex < textToType.length) {
          setTypedText(textToType.slice(0, currentIndex + 1));
          currentIndex++;
          timeout = setTimeout(typeNextChar, 80);
        } else {
          timeout = setTimeout(() => setStep(3), 500);
        }
      };
      timeout = setTimeout(typeNextChar, 300);
      
    } else if (step === 3) {
      // Step 3: Click Apply
      timeout = setTimeout(() => setStep(4), 600);
    } else if (step === 4) {
      // Step 4: Show Error
      timeout = setTimeout(() => {
        setStep(0);
        setTypedText("");
      }, 7000);
    }

    return () => clearTimeout(timeout);
  }, [step]);

  return (
    <section className="w-full py-24" style={{ background: "#111415" }}>
      <div className="max-w-[1440px] mx-auto px-6 flex flex-col gap-12">
        
        {/* Header */}
        <div className="flex flex-col gap-6">
          <div className="flex items-center gap-6 w-full">
            <span className="text-[#e3c0a0] text-[11px] tracking-[2.2px] uppercase font-mono">
              03 / SEE IT LIVE
            </span>
            <div className="flex-1 h-px bg-white/5"></div>
          </div>
          <h2
            className="text-[40px] md:text-[48px] leading-[1.2] text-[#e1e2e4]"
            style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
          >
            Watch Leaka catch a broken flow.
          </h2>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-8 border-b border-white/5 pb-4 mt-4">
          <button className="text-[#57f1db] text-[13px] font-mono font-bold tracking-wide border-b-2 border-[#57f1db] pb-4 -mb-[18px]">
            Checkout
          </button>
          <button className="text-[#bacac5] text-[13px] font-mono tracking-wide opacity-50 hover:opacity-100 transition-opacity pb-4 -mb-[18px]">
            Onboarding
          </button>
          <button className="text-[#bacac5] text-[13px] font-mono tracking-wide opacity-50 hover:opacity-100 transition-opacity pb-4 -mb-[18px]">
            Pricing
          </button>
        </div>

        {/* Main Panel */}
        <div className="grid grid-cols-1 lg:grid-cols-2 rounded-xl overflow-hidden border border-white/5 shadow-[0_0_40px_rgba(0,0,0,0.5)] mt-4 bg-[#141718]">
          
          {/* Left Pane: Browser Mock */}
          <div className="flex flex-col border-r border-white/5 relative group">
            {/* Hover Animated Inner Glow */}
            <div 
              className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none z-0" 
              style={{ background: 'radial-gradient(circle at center, rgba(87,241,219,0.02), transparent 70%)' }}
            />
            {/* Browser Top Bar */}
            <div className="flex items-center gap-4 px-4 py-3 border-b border-white/5 bg-[#181a1f] relative z-10">
              <div className="flex items-center gap-1.5">
                <div className="size-2.5 rounded-full bg-white/10"></div>
                <div className="size-2.5 rounded-full bg-white/10"></div>
                <div className="size-2.5 rounded-full bg-white/10"></div>
              </div>
              <div className="flex-1 bg-black/20 border border-white/5 rounded-md py-1.5 flex items-center justify-center">
                <span className="text-[11px] font-mono text-[#bacac5] opacity-60">checkout.example.com</span>
              </div>
            </div>

            {/* Browser Content */}
            <div className="flex-1 min-h-[440px] bg-[#0d1012] flex items-center justify-center p-8 relative overflow-hidden z-10">
              
              {step >= 1 && (
                <div className="w-full max-w-[380px] border border-white/10 rounded-xl p-8 bg-transparent shadow-2xl animate-in fade-in zoom-in-95 duration-500">
                  <h3 className="text-[#e1e2e4] text-[24px] mb-8" style={{ fontFamily: "Georgia, serif" }}>
                    Order Summary
                  </h3>
                  
                  <div className="flex flex-col gap-4 mb-6">
                    <div className="flex justify-between items-center text-[12px] font-mono text-[#bacac5]">
                      <span>Pro Plan (Annual)</span>
                      <span className="text-white">$120.00</span>
                    </div>
                    <div className="flex justify-between items-center text-[12px] font-mono text-[#bacac5]">
                      <span>Tax</span>
                      <span className="text-white">$10.80</span>
                    </div>
                  </div>

                  <div className="flex justify-between items-center border-t border-white/10 pt-6 mb-8 text-[12px] font-mono text-[#bacac5]">
                    <span>Total</span>
                    <span className="text-white font-bold">$130.80</span>
                  </div>

                  <div className="flex gap-3 mb-8 relative">
                    <div className="relative flex-1">
                      <input 
                        type="text" 
                        readOnly
                        value={typedText}
                        className={`w-full bg-black/20 border rounded-md px-3 py-2.5 text-[12px] font-mono outline-none transition-colors duration-300 ${
                          step === 4 ? 'border-red-500/50 text-red-200 shadow-[0_0_10px_rgba(239,68,68,0.1)]' : 'border-white/10 text-white'
                        }`}
                        placeholder={step >= 1 ? "Promo Code" : ""}
                      />
                      {step === 4 && (
                        <div className="absolute -right-2 -top-2 size-5 bg-[#ff8a8a] rounded-full flex items-center justify-center animate-in zoom-in duration-300 shadow-[0_0_10px_rgba(255,138,138,0.4)]">
                          <XCircle className="w-3.5 h-3.5 text-black" />
                        </div>
                      )}
                    </div>
                    <button 
                      className={`px-6 py-2.5 rounded-md text-[12px] font-mono font-bold transition-all duration-300 ${
                        step === 3 
                          ? 'bg-white/20 text-white scale-[0.98] border border-white/30 shadow-[0_0_15px_rgba(255,255,255,0.1)]' 
                          : 'bg-white/5 text-[#bacac5] border border-white/5 hover:bg-white/10'
                      }`}
                    >
                      Apply
                    </button>
                  </div>

                  <button className="w-full py-3.5 rounded-md bg-[#57f1db] text-[#0B0E14] text-[13px] font-mono font-bold hover:opacity-90 transition-opacity shadow-[0_0_15px_rgba(87,241,219,0.2)]">
                    Complete Order
                  </button>
                </div>
              )}

            </div>
          </div>

          {/* Right Pane: Trace Log */}
          <div className="flex flex-col bg-[#141718] relative group">
            <div 
              className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none z-0" 
              style={{ background: 'radial-gradient(circle at center, rgba(227,192,160,0.02), transparent 70%)' }}
            />
            <div className="flex items-center justify-between px-8 py-5 border-b border-white/5 relative z-10 bg-[#141718]/80 backdrop-blur-sm">
              <span className="text-[#bacac5] text-[10px] font-mono tracking-widest uppercase">Trace Log</span>
              <span className="text-[#bacac5] text-[10px] font-mono tracking-widest opacity-50">ID: TRC-8492-A</span>
            </div>
            
            <div className="flex flex-col p-8 gap-4 relative z-10">
              <LogStep active={step >= 0} text="Navigate to /checkout" time="120ms" />
              <LogStep active={step >= 1} text="Locate &quot;Promo Code&quot; input" time="45ms" />
              <LogStep active={step >= 2} text="Type &quot;WINTER24&quot;" time="110ms" />
              <LogStep active={step >= 3} text="Click &quot;Apply&quot;" time="80ms" />
              
              {step >= 4 && (
                <div className="mt-4 p-5 rounded-lg bg-[#30161a] border border-[#522125] animate-in fade-in slide-in-from-top-4 duration-500 shadow-[0_0_20px_rgba(239,68,68,0.05)]">
                  <div className="flex items-start gap-4">
                    <AlertCircle className="w-4 h-4 text-[#ff8a8a] shrink-0 mt-0.5" />
                    <div className="flex flex-col gap-2">
                      <span className="text-[#ffb3b3] text-[11px] font-mono leading-relaxed">
                        Expected a success message. None appeared — the promo code was never applied.
                      </span>
                      <span className="text-[#ff8a8a]/60 text-[10px] font-mono leading-relaxed">
                        Selector .success-toast not found. Network 500 on /api/promo/apply
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
          
        </div>
      </div>
    </section>
  );
}

function LogStep({ active, text, time }: { active: boolean, text: string, time: string }) {
  if (!active) return null;
  
  return (
    <div className="flex items-center justify-between animate-in fade-in slide-in-from-left-4 duration-500">
      <div className="flex items-center gap-4">
        <Check className="w-3.5 h-3.5 text-[#57f1db]" />
        <span className="text-[#e1e2e4] text-[12px] font-mono">{text}</span>
      </div>
      <span className="text-[#bacac5] opacity-50 text-[11px] font-mono">{time}</span>
    </div>
  );
}
