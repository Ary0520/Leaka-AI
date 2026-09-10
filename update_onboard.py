import sys

# We'll write the full page.tsx
content = '''"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/app/providers";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  ArrowRight, Sparkles, Zap, Bell, Mail, Ticket,
  FlaskConical, Loader2, CheckCircle2, ChevronRight,
  ChevronDown, Check, ShieldCheck, Network, Database
} from "lucide-react";
import { toast } from "@/components/ui/use-toast";

const TOTAL_STEPS = 5;
const ONBOARDING_KEY = "leaka_onboarding_done";

function StepDots({ current }: { current: number }) {
  return (
    <div className="flex items-center gap-2">
      {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
        <span
          key={i}
          className={ounded-full transition-all duration-300 }
        />
      ))}
    </div>
  );
}

function OnboardCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="w-full max-w-md bg-[#1d2021]/80 backdrop-blur-xl border border-[rgba(186,202,197,0.08)] rounded-2xl p-8 shadow-2xl flex flex-col gap-6">
      {children}
    </div>
  );
}

function SkipLink({ onSkip }: { onSkip: () => void }) {
  return (
    <button
      onClick={onSkip}
      className="text-sm text-[#bacac5] hover:text-[#e1e2e4] transition-colors"
    >
      Skip for now
    </button>
  );
}

// -- STEP 1: Connect AI --
function StepConnectAI({ onNext, onSkip }: { onNext: () => void; onSkip: () => void }) {
  const [provider, setProvider] = useState("openrouter");
  const [apiKey, setApiKey] = useState("");
  
  return (
    <OnboardCard>
      <div className="flex flex-col gap-1">
        <span className="text-[#57f1db] text-[11px] tracking-[2px] uppercase" style={{ fontFamily: "Georgia, serif" }}>Step 1 of 5</span>
        <h2 className="text-[28px] leading-[1.3] text-[#e1e2e4]" style={{ fontFamily: "Georgia, serif" }}>Setting up the AI Engine</h2>
        <p className="text-[#bacac5] text-sm">Leaka runs locally. Connect your LLM provider to power the AI Agent.</p>
      </div>
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label className="text-xs text-[#bacac5] uppercase tracking-wider">Provider</Label>
          <Select value={provider} onValueChange={setProvider}>
            <SelectTrigger className="bg-[#111415] border-[rgba(186,202,197,0.12)] text-[#e1e2e4]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-[#1d2021] border-[rgba(186,202,197,0.12)] text-[#e1e2e4]">
              <SelectItem value="openrouter">OpenRouter (Recommended)</SelectItem>
              <SelectItem value="openai">OpenAI</SelectItem>
              <SelectItem value="anthropic">Anthropic</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-2">
          <Label className="text-xs text-[#bacac5] uppercase tracking-wider">API Key</Label>
          <Input className="bg-[#111415] border-[rgba(186,202,197,0.12)] text-[#e1e2e4]" type="password" placeholder="sk-or-v1-..." value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
        </div>
      </div>
      <div className="flex items-center justify-between mt-2">
        <SkipLink onSkip={onSkip} />
        <Button onClick={onNext} className="gap-2 bg-[#e1e2e4] text-[#111415] hover:bg-white font-semibold">
          Next <ArrowRight className="w-4 h-4" />
        </Button>
      </div>
    </OnboardCard>
  );
}

// -- STEP 2: Kickoff --
function StepKickoff({ onNext, onSkip, setAppId, setEnvId }: { onNext: () => void; onSkip: () => void; setAppId: (id: number) => void; setEnvId: (id: number) => void; }) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleNext = async () => {
    if (!name || !url) return;
    setIsLoading(true);
    try {
      const app = await api.createApplication({ name, base_url: url });
      setAppId(app.id);
      const env = await api.createEnvironment(app.id, { name: "Staging", base_url: url });
      setEnvId(env.id);
      // Kickoff the background crawler!
      await api.exploreApplication(app.id, 40);
      onNext();
    } catch (e) {
      toast({ title: "Error", description: "Could not create application." });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <OnboardCard>
      <div className="flex flex-col gap-1">
        <span className="text-[#57f1db] text-[11px] tracking-[2px] uppercase" style={{ fontFamily: "Georgia, serif" }}>Step 2 of 5</span>
        <h2 className="text-[28px] leading-[1.3] text-[#e1e2e4]" style={{ fontFamily: "Georgia, serif" }}>Connect your Product</h2>
        <p className="text-[#bacac5] text-sm">We'll immediately spin up an autonomous agent to map your application in the background while you finish onboarding.</p>
      </div>
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label className="text-xs text-[#bacac5] uppercase tracking-wider">Product Name</Label>
          <Input className="bg-[#111415] border-[rgba(186,202,197,0.12)] text-[#e1e2e4]" placeholder="Acme E-Commerce" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="flex flex-col gap-2">
          <Label className="text-xs text-[#bacac5] uppercase tracking-wider">Staging URL</Label>
          <Input className="bg-[#111415] border-[rgba(186,202,197,0.12)] text-[#e1e2e4]" placeholder="https://staging.acme.com" type="url" value={url} onChange={(e) => setUrl(e.target.value)} />
        </div>
      </div>
      <div className="flex items-center justify-between mt-2">
        <SkipLink onSkip={onSkip} />
        <Button disabled={!name || !url || isLoading} onClick={handleNext} className="gap-2 bg-[#57f1db] text-[#111415] hover:bg-[#57f1db]/90 font-semibold">
          {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Start Mapping <Zap className="w-4 h-4" /></>}
        </Button>
      </div>
    </OnboardCard>
  );
}

// -- STEP 3: Auth Wallet --
function StepAuthWallet({ onNext, onSkip, appId, envId }: { onNext: () => void; onSkip: () => void; appId: number | null; envId: number | null; }) {
  const [apiUrl, setApiUrl] = useState("");
  const [payload, setPayload] = useState("{\\n  \\"email\\": \\"test@acme.com\\",\\n  \\"password\\": \\"password123\\"\\n}");
  const [tokenPath, setTokenPath] = useState("data.access_token");
  const [isLoading, setIsLoading] = useState(false);

  const handleNext = async () => {
    if (!apiUrl || !appId || !envId) return onSkip();
    setIsLoading(true);
    try {
      await api.updateEnvironment(appId, envId, {
        auth_strategy: "api_injection",
        auth_api_url: apiUrl,
        auth_payload: payload,
        auth_token_path: tokenPath,
      });
      onNext();
    } catch (e) {
      toast({ title: "Error saving Auth Wallet" });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <OnboardCard>
      <div className="flex flex-col gap-1">
        <span className="text-[#57f1db] text-[11px] tracking-[2px] uppercase" style={{ fontFamily: "Georgia, serif" }}>Step 3 of 5</span>
        <h2 className="text-[28px] leading-[1.3] text-[#e1e2e4]" style={{ fontFamily: "Georgia, serif" }}>The Auth Wallet</h2>
        <p className="text-[#bacac5] text-sm">Leaka injects authentication directly into the browser memory. No flakiness with UI logins or 2FA.</p>
      </div>
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label className="text-xs text-[#bacac5] uppercase tracking-wider">Auth API Endpoint</Label>
          <Input className="bg-[#111415] border-[rgba(186,202,197,0.12)] text-[#e1e2e4]" placeholder="https://api.acme.com/v1/login" value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} />
        </div>
        <div className="flex flex-col gap-2">
          <Label className="text-xs text-[#bacac5] uppercase tracking-wider">JSON Payload</Label>
          <Textarea className="bg-[#111415] border-[rgba(186,202,197,0.12)] text-[#e1e2e4] font-mono text-xs h-24" value={payload} onChange={(e) => setPayload(e.target.value)} />
        </div>
        <div className="flex flex-col gap-2">
          <Label className="text-xs text-[#bacac5] uppercase tracking-wider">Token Path</Label>
          <Input className="bg-[#111415] border-[rgba(186,202,197,0.12)] text-[#e1e2e4] font-mono" placeholder="data.access_token" value={tokenPath} onChange={(e) => setTokenPath(e.target.value)} />
        </div>
      </div>
      <div className="flex items-center justify-between mt-2">
        <SkipLink onSkip={onSkip} />
        <Button disabled={isLoading} onClick={handleNext} className="gap-2 bg-[#e1e2e4] text-[#111415] hover:bg-white font-semibold">
          {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Save & Next <ShieldCheck className="w-4 h-4" /></>}
        </Button>
      </div>
    </OnboardCard>
  );
}

// -- STEP 4: Company Brain --
function StepCompanyBrain({ onNext, onSkip, appId }: { onNext: () => void; onSkip: () => void; appId: number | null; }) {
  const [spec, setSpec] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleNext = async () => {
    if (!spec || !appId) return onSkip();
    setIsLoading(true);
    try {
      await api.updateApplication(appId, { openapi_spec: spec });
      onNext();
    } catch (e) {
      toast({ title: "Error saving Brain" });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <OnboardCard>
      <div className="flex flex-col gap-1">
        <span className="text-[#57f1db] text-[11px] tracking-[2px] uppercase" style={{ fontFamily: "Georgia, serif" }}>Step 4 of 5</span>
        <h2 className="text-[28px] leading-[1.3] text-[#e1e2e4]" style={{ fontFamily: "Georgia, serif" }}>The Company Brain</h2>
        <p className="text-[#bacac5] text-sm">Upload your Swagger/OpenAPI JSON. This gives Leaka 10x smarter Root Cause Analysis and enables Automatic Test Data generation.</p>
      </div>
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label className="text-xs text-[#bacac5] uppercase tracking-wider">OpenAPI JSON Spec</Label>
          <Textarea className="bg-[#111415] border-[rgba(186,202,197,0.12)] text-[#e1e2e4] font-mono text-xs h-32" placeholder="{ \\"openapi\\": \\"3.0.0\\", ... }" value={spec} onChange={(e) => setSpec(e.target.value)} />
        </div>
      </div>
      <div className="flex items-center justify-between mt-2">
        <SkipLink onSkip={onSkip} />
        <Button disabled={isLoading} onClick={handleNext} className="gap-2 bg-[#e1e2e4] text-[#111415] hover:bg-white font-semibold">
          {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Save & Next <Database className="w-4 h-4" /></>}
        </Button>
      </div>
    </OnboardCard>
  );
}

// -- STEP 5: Aha! Moment --
function StepAhaMoment({ onFinish, appId }: { onFinish: () => void; appId: number | null; }) {
  const { data: graphData, isLoading } = useQuery({
    queryKey: ["app-graph", appId],
    queryFn: () => appId ? api.getApplicationGraph(appId) : null,
    enabled: !!appId,
    refetchInterval: 3000, // Poll to see nodes mapping live!
  });

  const nodeCount = graphData?.nodes?.length || 0;

  return (
    <OnboardCard>
      <div className="flex flex-col items-center justify-center text-center gap-4 py-4">
        <div className="h-16 w-16 bg-[#57f1db]/10 rounded-full flex items-center justify-center mb-2">
          <Network className="w-8 h-8 text-[#57f1db]" />
        </div>
        <h2 className="text-[28px] leading-[1.3] text-[#e1e2e4]" style={{ fontFamily: "Georgia, serif" }}>Leaka has mapped your app.</h2>
        <p className="text-[#bacac5] text-sm">
          While you were configuring your wallet, the autonomous agent found <span className="text-white font-bold">{nodeCount}</span> critical revenue nodes.
        </p>

        <div className="w-full bg-[#111415] border border-[rgba(186,202,197,0.12)] rounded-lg p-4 mt-2 text-left">
          <p className="text-xs text-[#bacac5] uppercase tracking-wider mb-3">Top Recommended E2E Tests</p>
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2 p-2 bg-[#1d2021] rounded border border-[rgba(186,202,197,0.08)]"><CheckCircle2 className="w-4 h-4 text-[#57f1db]" /><span className="text-sm text-[#e1e2e4]">User Checkout Flow</span></div>
            <div className="flex items-center gap-2 p-2 bg-[#1d2021] rounded border border-[rgba(186,202,197,0.08)]"><CheckCircle2 className="w-4 h-4 text-[#57f1db]" /><span className="text-sm text-[#e1e2e4]">Password Reset Flow</span></div>
            <div className="flex items-center gap-2 p-2 bg-[#1d2021] rounded border border-[rgba(186,202,197,0.08)]"><CheckCircle2 className="w-4 h-4 text-[#57f1db]" /><span className="text-sm text-[#e1e2e4]">Add to Cart Flow</span></div>
          </div>
        </div>

      </div>
      <div className="flex items-center justify-center mt-2">
        <Button onClick={onFinish} className="gap-2 w-full bg-[#57f1db] text-[#111415] hover:bg-[#57f1db]/90 font-semibold">
          Go to dashboard <Sparkles className="w-4 h-4" />
        </Button>
      </div>
    </OnboardCard>
  );
}

export default function OnboardPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [step, setStep] = useState(0);
  const [appId, setAppId] = useState<number | null>(null);
  const [envId, setEnvId] = useState<number | null>(null);
  const [redirecting, setRedirecting] = useState(true);

  const { data: onboardingData, isLoading: onboardingLoading } = useQuery({
    queryKey: ["onboarding-status"],
    queryFn: () => api.getOnboardingStatus(),
    enabled: !!user,
  });

  const completeMut = useMutation({
    mutationFn: () => api.completeOnboarding(),
  });

  useEffect(() => {
    if (authLoading || onboardingLoading) return;
    if (!user) { router.replace("/login"); return; }
    if (onboardingData?.onboarding_completed) { router.replace("/dashboard"); return; }
    setRedirecting(false);
  }, [authLoading, onboardingLoading, user, onboardingData, router]);

  const finish = async () => {
    try { await completeMut.mutateAsync(); } catch {}
    if (typeof window !== "undefined") localStorage.setItem(ONBOARDING_KEY, "1");
    router.replace("/dashboard");
  };

  if (redirecting || authLoading || onboardingLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "#111415" }}>
        <Loader2 className="w-6 h-6 text-[#57f1db] animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12" style={{ background: "#111415" }}>
      <div className="fixed inset-0 pointer-events-none" style={{ backgroundImage: "radial-gradient(ellipse 600px 400px at 60% 20%, rgba(45,212,191,0.06) 0%, transparent 70%)" }} />
      <div className="mb-8 flex flex-col items-center gap-2 relative z-10">
        <span className="text-[#e1e2e4] text-lg font-medium" style={{ fontFamily: "Georgia, serif" }}>Leaka AI</span>
        <StepDots current={step} />
      </div>
      <div className="relative z-10 w-full flex justify-center">
        {step === 0 && <StepConnectAI onNext={() => setStep(1)} onSkip={() => setStep(1)} />}
        {step === 1 && <StepKickoff onNext={() => setStep(2)} onSkip={() => setStep(2)} setAppId={setAppId} setEnvId={setEnvId} />}
        {step === 2 && <StepAuthWallet onNext={() => setStep(3)} onSkip={() => setStep(3)} appId={appId} envId={envId} />}
        {step === 3 && <StepCompanyBrain onNext={() => setStep(4)} onSkip={() => setStep(4)} appId={appId} />}
        {step === 4 && <StepAhaMoment onFinish={finish} appId={appId} />}
      </div>
    </div>
  );
}
'''

with open('frontend/src/app/onboard/page.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Updated onboard/page.tsx')
