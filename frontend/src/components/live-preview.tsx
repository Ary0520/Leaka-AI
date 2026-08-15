"use client";

import React, { useState, useEffect } from "react";
import { Check, AlertCircle, XCircle, Camera as CameraIcon, Crosshair } from "lucide-react";

type TabName = "checkout" | "onboarding" | "pricing";

export function LivePreview() {
  const [activeTab, setActiveTab] = useState<TabName>("checkout");
  const [step, setStep] = useState(0);
  const [typedText, setTypedText] = useState("");
  const [cameraFlash, setCameraFlash] = useState(false);

  // Reset state when tab changes
  useEffect(() => {
    setStep(0);
    setTypedText("");
    setCameraFlash(false);
  }, [activeTab]);

  // Timeline orchestration
  useEffect(() => {
    let timeout: NodeJS.Timeout;

    if (activeTab === "checkout") {
      if (step === 0) timeout = setTimeout(() => setStep(1), 1000); // Load UI
      else if (step === 1) timeout = setTimeout(() => setStep(2), 1200); // Locate input (Vision)
      else if (step === 2) { // Type
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
      }
      else if (step === 3) timeout = setTimeout(() => setStep(4), 800); // Locate button (Vision)
      else if (step === 4) timeout = setTimeout(() => setStep(5), 800); // Click apply
      else if (step === 5) {
        setCameraFlash(true);
        setTimeout(() => setCameraFlash(false), 300);
        timeout = setTimeout(() => setStep(0), 7000); // Error state & loop
      }
    } 
    
    else if (activeTab === "onboarding") {
      if (step === 0) timeout = setTimeout(() => setStep(1), 1000); // Load UI
      else if (step === 1) timeout = setTimeout(() => setStep(2), 1200); // Locate email
      else if (step === 2) { // Type
        const textToType = "user@example.com";
        let currentIndex = 0;
        const typeNextChar = () => {
          if (currentIndex < textToType.length) {
            setTypedText(textToType.slice(0, currentIndex + 1));
            currentIndex++;
            timeout = setTimeout(typeNextChar, 60);
          } else {
            timeout = setTimeout(() => setStep(3), 500);
          }
        };
        timeout = setTimeout(typeNextChar, 300);
      }
      else if (step === 3) timeout = setTimeout(() => setStep(4), 600); // Click sign up
      else if (step === 4) timeout = setTimeout(() => setStep(5), 2500); // Spinner waiting
      else if (step === 5) {
        setCameraFlash(true);
        setTimeout(() => setCameraFlash(false), 300);
        timeout = setTimeout(() => setStep(0), 7000); // Error state & loop
      }
    }

    else if (activeTab === "pricing") {
      if (step === 0) timeout = setTimeout(() => setStep(1), 1000); // Load UI
      else if (step === 1) timeout = setTimeout(() => setStep(2), 1200); // Locate toggle
      else if (step === 2) timeout = setTimeout(() => setStep(3), 800); // Click toggle
      else if (step === 3) timeout = setTimeout(() => setStep(4), 800); // Locate Pro button
      else if (step === 4) timeout = setTimeout(() => setStep(5), 1000); // Click & show modal
      else if (step === 5) {
        setCameraFlash(true);
        setTimeout(() => setCameraFlash(false), 300);
        timeout = setTimeout(() => setStep(0), 7000); // Error state & loop
      }
    }

    return () => clearTimeout(timeout);
  }, [step, activeTab]);

  return (
    <section className="w-full py-24 relative overflow-hidden" style={{ background: "#111415" }}>
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
        <div className="flex items-center gap-8 border-b border-white/5 pb-4 mt-4 relative z-10">
          {(["checkout", "onboarding", "pricing"] as TabName[]).map((tab) => (
            <button
              key={tab}
              onClick={() => { setActiveTab(tab); setStep(0); }}
              className={`text-[13px] font-mono tracking-wide pb-4 -mb-[18px] transition-all duration-300 ${
                activeTab === tab 
                  ? "text-[#57f1db] font-bold border-b-2 border-[#57f1db]" 
                  : "text-[#bacac5] opacity-50 hover:opacity-100"
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {/* Main Panel */}
        <div className="grid grid-cols-1 lg:grid-cols-2 rounded-xl overflow-hidden border border-white/5 shadow-[0_0_50px_rgba(0,0,0,0.6)] mt-4 bg-[#141718] min-h-[550px]">
          
          {/* Left Pane: Browser Mock */}
          <div className="flex flex-col border-r border-white/5 relative group bg-[#0d1012] overflow-hidden">
            {/* Camera Flash overlay (confined to browser) */}
            <div 
              className={`absolute inset-0 bg-white z-[100] pointer-events-none transition-opacity duration-300 ${
                cameraFlash ? "opacity-20" : "opacity-0"
              }`} 
            />
            
            {/* Browser Top Bar */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-[#181a1f] relative z-20">
              <div className="flex items-center gap-4 w-full">
                <div className="flex items-center gap-1.5 shrink-0">
                  <div className="size-2.5 rounded-full bg-white/10"></div>
                  <div className="size-2.5 rounded-full bg-white/10"></div>
                  <div className="size-2.5 rounded-full bg-white/10"></div>
                </div>
                <div className="flex-1 bg-black/20 border border-white/5 rounded-md py-1.5 flex items-center justify-center relative overflow-hidden">
                  <span className="text-[11px] font-mono text-[#bacac5] opacity-60">
                    {activeTab === "checkout" ? "checkout.example.com" : activeTab === "onboarding" ? "app.example.com/signup" : "example.com/pricing"}
                  </span>
                </div>
              </div>
            </div>

            {/* Live Agent Status Bar */}
            <div className="w-full bg-[#57f1db]/10 border-b border-[#57f1db]/20 py-1.5 px-4 flex items-center gap-3 relative z-20">
              <div className="size-2 bg-[#57f1db] rounded-full animate-pulse shadow-[0_0_8px_rgba(87,241,219,0.8)]" />
              <span className="text-[#57f1db] text-[10px] font-mono uppercase tracking-widest">
                Agent Status: {
                  activeTab === "checkout" ? (
                    step === 0 ? "Navigating to /checkout..." :
                    step === 1 ? "Computer Vision scanning DOM for 'Promo Code' input..." :
                    step === 2 ? "Simulating human keyboard input..." :
                    step === 3 ? "Locating 'Apply' button..." :
                    step === 4 ? "Clicking 'Apply'..." :
                    "Anomaly detected. Capturing DOM snapshot..."
                  ) : activeTab === "onboarding" ? (
                    step === 0 ? "Navigating to /signup..." :
                    step === 1 ? "Targeting 'Email' field..." :
                    step === 2 ? "Typing credentials..." :
                    step === 3 ? "Clicking 'Sign Up'..." :
                    step === 4 ? "Waiting for dashboard to load..." :
                    "Timeout detected. Capturing DOM snapshot..."
                  ) : (
                    step === 0 ? "Navigating to /pricing..." :
                    step === 1 ? "Targeting 'Annual' toggle..." :
                    step === 2 ? "Toggling selection..." :
                    step === 3 ? "Targeting 'Pro' plan upgrade button..." :
                    step === 4 ? "Awaiting modal appearance..." :
                    "Text mismatch detected. Capturing DOM snapshot..."
                  )
                }
              </span>
            </div>

            {/* Browser Content Workspace */}
            <div className="flex-1 flex items-center justify-center p-8 relative overflow-hidden z-10">
              
              {/* === CHECKOUT MOCK === */}
              {activeTab === "checkout" && step >= 1 && (
                <div className="w-full max-w-[380px] border border-white/10 rounded-xl p-8 bg-[#141718]/80 shadow-2xl animate-in fade-in zoom-in-95 duration-500 relative">
                  <h3 className="text-[#e1e2e4] text-[24px] mb-8" style={{ fontFamily: "Georgia, serif" }}>Order Summary</h3>
                  
                  <div className="flex flex-col gap-4 mb-6">
                    <div className="flex justify-between items-center text-[12px] font-mono text-[#bacac5]">
                      <span>Pro Plan (Annual)</span><span className="text-white">$120.00</span>
                    </div>
                    <div className="flex justify-between items-center text-[12px] font-mono text-[#bacac5]">
                      <span>Tax</span><span className="text-white">$10.80</span>
                    </div>
                  </div>
                  <div className="flex justify-between items-center border-t border-white/10 pt-6 mb-8 text-[12px] font-mono text-[#bacac5]">
                    <span>Total</span><span className="text-white font-bold">$130.80</span>
                  </div>

                  <div className="flex gap-3 mb-8 relative">
                    <div className="relative flex-1">
                      {/* Vision Box */}
                      {step === 1 && <VisionBox label="input#promo" />}
                      <input 
                        type="text" readOnly value={typedText}
                        className={`w-full bg-black/20 border rounded-md px-3 py-2.5 text-[12px] font-mono outline-none transition-colors duration-300 ${
                          step >= 5 ? 'border-red-500/50 text-red-200 shadow-[0_0_10px_rgba(239,68,68,0.1)]' : 'border-white/10 text-white'
                        }`}
                        placeholder="Promo Code"
                      />
                      {step >= 5 && (
                        <div className="absolute -right-2 -top-2 size-5 bg-[#ff8a8a] rounded-full flex items-center justify-center animate-in zoom-in duration-300 shadow-[0_0_10px_rgba(255,138,138,0.4)] z-50">
                          <XCircle className="w-3.5 h-3.5 text-black" />
                        </div>
                      )}
                    </div>
                    <div className="relative">
                      {/* Vision Box */}
                      {step === 3 && <VisionBox label="btn.apply" />}
                      <button 
                        className={`px-6 py-2.5 rounded-md text-[12px] font-mono font-bold transition-all duration-300 ${
                          step === 4 ? 'bg-white/20 text-white scale-[0.95] border border-white/30' : 'bg-white/5 text-[#bacac5] border border-white/5'
                        }`}
                      >
                        Apply
                      </button>
                    </div>
                  </div>
                  <button className="w-full py-3.5 rounded-md bg-[#57f1db] text-[#0B0E14] text-[13px] font-mono font-bold opacity-50 cursor-not-allowed">
                    Complete Order
                  </button>
                </div>
              )}

              {/* === ONBOARDING MOCK === */}
              {activeTab === "onboarding" && step >= 1 && (
                <div className="w-full max-w-[340px] border border-white/10 rounded-xl p-8 bg-[#141718]/80 shadow-2xl animate-in fade-in zoom-in-95 duration-500 relative flex flex-col items-center">
                  <div className="size-10 rounded-xl bg-white/5 flex items-center justify-center mb-6">
                    <div className="size-4 bg-white rounded-full" />
                  </div>
                  <h3 className="text-[#e1e2e4] text-[20px] mb-8" style={{ fontFamily: "Georgia, serif" }}>Create an account</h3>
                  
                  <div className="w-full flex flex-col gap-4 mb-8">
                    <div className="relative w-full">
                      {step === 1 && <VisionBox label="input[type='email']" />}
                      <input 
                        type="text" readOnly value={typedText}
                        className="w-full bg-black/20 border border-white/10 rounded-md px-4 py-3 text-[12px] font-mono text-white outline-none"
                        placeholder="Email address"
                      />
                    </div>
                    <input 
                      type="password" readOnly value="••••••••"
                      className="w-full bg-black/20 border border-white/10 rounded-md px-4 py-3 text-[12px] font-mono text-white outline-none opacity-50"
                      placeholder="Password"
                    />
                  </div>
                  <div className="relative w-full">
                    {step === 3 && <VisionBox label="btn.signup" />}
                    <button 
                      className={`w-full py-3.5 rounded-md bg-white text-black text-[13px] font-mono font-bold transition-all duration-300 flex justify-center items-center h-[46px] ${
                        step >= 4 ? 'opacity-80' : ''
                      }`}
                    >
                      {step >= 4 ? (
                        <div className="size-4 border-2 border-black/20 border-t-black rounded-full animate-spin" />
                      ) : "Sign Up"}
                    </button>
                    {step === 5 && (
                      <div className="absolute -right-2 -top-2 size-5 bg-[#ff8a8a] rounded-full flex items-center justify-center animate-in zoom-in duration-300 shadow-[0_0_10px_rgba(255,138,138,0.4)] z-50">
                        <XCircle className="w-3.5 h-3.5 text-black" />
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* === PRICING MOCK === */}
              {activeTab === "pricing" && step >= 1 && (
                <div className="w-full max-w-[440px] flex flex-col items-center animate-in fade-in zoom-in-95 duration-500">
                  
                  {/* Toggle */}
                  <div className="relative mb-8">
                    {step === 1 && <VisionBox label="switch#billing" />}
                    <div className="flex items-center gap-3 bg-white/5 p-1 rounded-full border border-white/5">
                      <div className={`px-4 py-1.5 rounded-full text-[11px] font-mono transition-colors ${step < 2 ? 'bg-white/10 text-white' : 'text-[#bacac5]'}`}>Monthly</div>
                      <div className={`px-4 py-1.5 rounded-full text-[11px] font-mono transition-colors ${step >= 2 ? 'bg-[#57f1db]/20 text-[#57f1db]' : 'text-[#bacac5]'}`}>Annual</div>
                    </div>
                  </div>

                  <div className="flex gap-4 w-full">
                    {/* Free Plan */}
                    <div className="flex-1 border border-white/5 bg-black/20 rounded-xl p-5 opacity-50">
                      <div className="text-[14px] font-bold text-white mb-2">Free</div>
                      <div className="text-[20px] font-mono text-white mb-4">$0<span className="text-[10px] text-[#bacac5]">/mo</span></div>
                      <button className="w-full py-2 bg-white/5 rounded text-[11px] font-mono">Current Plan</button>
                    </div>
                    {/* Pro Plan */}
                    <div className="flex-1 border border-[#57f1db]/30 bg-[#57f1db]/5 rounded-xl p-5 relative">
                      <div className="text-[14px] font-bold text-[#57f1db] mb-2">Pro</div>
                      <div className="text-[20px] font-mono text-white mb-4">{step >= 2 ? "$29" : "$39"}<span className="text-[10px] text-[#bacac5]">/mo</span></div>
                      <div className="relative mt-2">
                        {step === 3 && <VisionBox label="btn[data-plan='pro']" />}
                        <button className={`w-full py-2 bg-[#57f1db] text-black rounded text-[11px] font-mono font-bold transition-transform ${step === 4 ? 'scale-95' : ''}`}>
                          Upgrade
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Wrong Modal Popover */}
                  {step >= 5 && (
                    <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-[2px] animate-in fade-in duration-300">
                      <div className="bg-[#181a1f] border border-[#ff8a8a]/30 p-6 rounded-xl shadow-2xl flex flex-col items-center relative">
                        <VisionBox label="Assertion Failed" color="#ff8a8a" />
                        <div className="size-12 rounded-full bg-[#ff8a8a]/10 flex items-center justify-center mb-4">
                          <Check className="w-6 h-6 text-[#ff8a8a]" />
                        </div>
                        <h4 className="text-white text-[16px] font-bold mb-1">Success!</h4>
                        <p className="text-[#ff8a8a] text-[12px] font-mono">Free Plan Activated</p>
                      </div>
                    </div>
                  )}
                </div>
              )}

            </div>
          </div>

          {/* Right Pane: Trace Log */}
          <div className="flex flex-col bg-[#141718] relative group">
            <div className="flex items-center justify-between px-8 py-5 border-b border-white/5 relative z-10 bg-[#141718]">
              <span className="text-[#bacac5] text-[10px] font-mono tracking-widest uppercase flex items-center gap-2">
                <Crosshair className="w-3.5 h-3.5 text-[#57f1db]" /> Trace Log
              </span>
              <span className="text-[#bacac5] text-[10px] font-mono tracking-widest opacity-50 flex items-center gap-2">
                ID: TRC-8492-{activeTab === "checkout" ? "C" : activeTab === "onboarding" ? "O" : "P"} 
              </span>
            </div>
            
            <div className="flex flex-col p-8 gap-4 relative z-10 overflow-y-auto">
              
              {/* CHECKOUT LOGS */}
              {activeTab === "checkout" && (
                <>
                  <LogStep active={step >= 0} text="Navigate to /checkout" time="120ms" />
                  <LogStep active={step >= 1} text="Locate &quot;Promo Code&quot; input" time="45ms" />
                  <LogStep active={step >= 2} text="Type &quot;WINTER24&quot;" time="110ms" />
                  <LogStep active={step >= 3} text="Locate &quot;Apply&quot; button" time="32ms" />
                  <LogStep active={step >= 4} text="Click &quot;Apply&quot;" time="80ms" />
                  
                  {step >= 5 && (
                    <ErrorLog 
                      title="Expected a success message. None appeared — the promo code was never applied." 
                      detail="Selector .success-toast not found. Network 500 on /api/promo/apply" 
                    />
                  )}
                </>
              )}

              {/* ONBOARDING LOGS */}
              {activeTab === "onboarding" && (
                <>
                  <LogStep active={step >= 0} text="Navigate to /signup" time="150ms" />
                  <LogStep active={step >= 1} text="Locate &quot;Email&quot; input" time="38ms" />
                  <LogStep active={step >= 2} text="Type credentials" time="185ms" />
                  <LogStep active={step >= 3} text="Click &quot;Sign Up&quot;" time="65ms" />
                  <LogStep active={step >= 4} text="Wait for dashboard load" time="10000ms" inProgress={step === 4} />
                  
                  {step >= 5 && (
                    <ErrorLog 
                      title="Timeout: User dashboard did not load within 10000ms." 
                      detail="Sign up flow hung on loading state. Network requests stalled." 
                    />
                  )}
                </>
              )}

              {/* PRICING LOGS */}
              {activeTab === "pricing" && (
                <>
                  <LogStep active={step >= 0} text="Navigate to /pricing" time="90ms" />
                  <LogStep active={step >= 1} text="Locate &quot;Annual&quot; toggle" time="42ms" />
                  <LogStep active={step >= 2} text="Click toggle" time="55ms" />
                  <LogStep active={step >= 3} text="Locate &quot;Pro&quot; upgrade button" time="30ms" />
                  <LogStep active={step >= 4} text="Click &quot;Upgrade&quot; & assert success" time="120ms" />
                  
                  {step >= 5 && (
                    <ErrorLog 
                      title="Assertion Failed: Expected 'Pro Plan', found 'Free Plan'." 
                      detail="Modal text mismatch. Button fired the wrong plan payload." 
                    />
                  )}
                </>
              )}

            </div>
          </div>
          
        </div>
      </div>
    </section>
  );
}

// Subcomponents

function LogStep({ active, text, time, inProgress = false }: { active: boolean, text: string, time: string, inProgress?: boolean }) {
  if (!active) return null;
  
  return (
    <div className="flex items-center justify-between animate-in fade-in slide-in-from-left-4 duration-500">
      <div className="flex items-center gap-4">
        {inProgress ? (
          <div className="w-3.5 h-3.5 rounded-full border-2 border-[#bacac5]/30 border-t-[#57f1db] animate-spin" />
        ) : (
          <Check className="w-3.5 h-3.5 text-[#57f1db]" />
        )}
        <span className={`text-[12px] font-mono ${inProgress ? 'text-[#bacac5] opacity-80' : 'text-[#e1e2e4]'}`}>{text}</span>
      </div>
      <span className="text-[#bacac5] opacity-50 text-[11px] font-mono">{time}</span>
    </div>
  );
}

function ErrorLog({ title, detail }: { title: string, detail: string }) {
  return (
    <div className="mt-4 p-5 rounded-lg bg-[#30161a] border border-[#522125] animate-in fade-in slide-in-from-top-4 duration-500 shadow-[0_0_20px_rgba(239,68,68,0.05)] relative overflow-hidden">
      <div className="absolute top-0 left-0 w-1 h-full bg-[#ff8a8a]" />
      <div className="flex items-start gap-4">
        <AlertCircle className="w-4 h-4 text-[#ff8a8a] shrink-0 mt-0.5" />
        <div className="flex flex-col gap-2">
          <span className="text-[#ffb3b3] text-[11px] font-mono leading-relaxed">{title}</span>
          <span className="text-[#ff8a8a]/60 text-[10px] font-mono leading-relaxed">{detail}</span>
        </div>
      </div>
      <div className="mt-4 flex items-center gap-2 pt-4 border-t border-[#ff8a8a]/10">
        <CameraIcon className="w-3.5 h-3.5 text-[#ff8a8a]/80" />
        <span className="text-[#ff8a8a]/80 text-[10px] font-mono uppercase tracking-wider">DOM Snapshot Captured</span>
      </div>
    </div>
  );
}

function VisionBox({ label, color = "#57f1db" }: { label: string, color?: string }) {
  return (
    <div 
      className="absolute -inset-1.5 z-50 pointer-events-none animate-pulse"
      style={{ border: `1.5px solid ${color}`, backgroundColor: `${color}10` }}
    >
      <div 
        className="absolute -top-5 right-0 text-[9px] font-mono px-1.5 py-0.5 text-[#0B0E14] font-bold flex items-center gap-1 shadow-lg whitespace-nowrap"
        style={{ backgroundColor: color }}
      >
        <Crosshair className="w-2.5 h-2.5" /> {label}
      </div>
      {/* Corner accents */}
      <div className="absolute -top-1 -left-1 size-2 border-t-2 border-l-2" style={{ borderColor: color }} />
      <div className="absolute -top-1 -right-1 size-2 border-t-2 border-r-2" style={{ borderColor: color }} />
      <div className="absolute -bottom-1 -left-1 size-2 border-b-2 border-l-2" style={{ borderColor: color }} />
      <div className="absolute -bottom-1 -right-1 size-2 border-b-2 border-r-2" style={{ borderColor: color }} />
    </div>
  );
}
