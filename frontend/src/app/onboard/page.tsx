"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/app/providers";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  ArrowRight, Sparkles, Zap, Bell, Mail, Ticket,
  FlaskConical, Loader2, CheckCircle2, ChevronRight,
  ChevronDown, Check,
} from "lucide-react";
import { toast } from "@/components/ui/use-toast";

// ── Constants ─────────────────────────────────────────────────────────────────
const TOTAL_STEPS = 3;
const ONBOARDING_KEY = "leaka_onboarding_done";

// ── Step indicator ─────────────────────────────────────────────────────────────
function StepDots({ current }: { current: number }) {
  return (
    <div className="flex items-center gap-2">
      {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
        <span
          key={i}
          className={`rounded-full transition-all duration-300 ${
            i < current
              ? "w-2 h-2 bg-[#57f1db]"
              : i === current
              ? "w-6 h-2 bg-[#57f1db]"
              : "w-2 h-2 bg-[#3c4a46]"
          }`}
        />
      ))}
    </div>
  );
}

// ── Skip link ─────────────────────────────────────────────────────────────────
function SkipLink({ onSkip }: { onSkip: () => void }) {
  return (
    <button
      onClick={onSkip}
      className="text-xs text-[#3c4a46] hover:text-[#bacac5] transition-colors underline underline-offset-2"
    >
      Skip for now
    </button>
  );
}

// ── Shared card wrapper ────────────────────────────────────────────────────────
function OnboardCard({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="w-full max-w-lg rounded-2xl p-8 flex flex-col gap-6"
      style={{
        background: "rgba(29,32,33,0.6)",
        border: "1px solid rgba(186,202,197,0.08)",
        backdropFilter: "blur(16px)",
      }}
    >
      {children}
    </div>
  );
}

// ── Step 1 — Welcome ──────────────────────────────────────────────────────────
function StepWelcome({ onNext, onSkip }: { onNext: () => void; onSkip: () => void }) {
  return (
    <OnboardCard>
      <div className="flex flex-col gap-3">
        <span
          className="text-[#57f1db] text-[11px] tracking-[2px] uppercase"
          style={{ fontFamily: "Georgia, serif" }}
        >
          Welcome to Leaka AI
        </span>
        <h1
          className="text-[36px] leading-[1.2] text-[#e1e2e4]"
          style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
        >
          Autonomous QA for
          <br />
          revenue-critical flows.
        </h1>
        <p className="text-[#bacac5] text-[16px] leading-[1.6]">
          Write a test in plain English. Leaka navigates your website, executes it, and gives you visual proof when something breaks.
        </p>
      </div>

      <div
        className="rounded-xl p-4 flex flex-col gap-2 text-sm text-[#bacac5]"
        style={{ background: "rgba(87,241,219,0.04)", border: "1px solid rgba(87,241,219,0.08)" }}
      >
        {[
          "No selectors. No code.",
          "Self-heals when UI changes.",
          "Screenshots + steps on every failure.",
          "Alerts your team automatically.",
        ].map((f) => (
          <div key={f} className="flex items-center gap-2">
            <Check className="w-3.5 h-3.5 text-[#57f1db] shrink-0" />
            <span>{f}</span>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <SkipLink onSkip={onSkip} />
        <Button
          onClick={onNext}
          className="gap-2 bg-[#57f1db] text-[#111415] hover:bg-[#57f1db]/90 font-semibold"
        >
          Get started <ArrowRight className="w-4 h-4" />
        </Button>
      </div>
    </OnboardCard>
  );
}

// ── Step 2 — Connect AI ───────────────────────────────────────────────────────
function StepConnectAI({ onNext, onSkip }: { onNext: () => void; onSkip: () => void }) {
  const [provider, setProvider] = useState("openrouter");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("openai/gpt-4o");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; detail: string } | null>(null);

  const saveMut = useMutation({
    mutationFn: () =>
      api.updateIntegrationSettings({
        llm_provider: provider,
        openrouter_api_key: provider === "openrouter" ? apiKey : undefined,
        openai_api_key: provider === "openai" ? apiKey : undefined,
        anthropic_api_key: provider === "anthropic" ? apiKey : undefined,
        llm_model_openrouter: provider === "openrouter" ? model : undefined,
      }),
  });

  const testMut = useMutation({
    mutationFn: async () => {
      // Save settings first so the backend reads the latest key, then test
      await api.updateIntegrationSettings({
        llm_provider: provider,
        openrouter_api_key: provider === "openrouter" ? apiKey : undefined,
        openai_api_key: provider === "openai" ? apiKey : undefined,
        anthropic_api_key: provider === "anthropic" ? apiKey : undefined,
        llm_model_openrouter: provider === "openrouter" ? model : undefined,
      });
      return api.testLlmConnection();
    },
    onSuccess: (r) => setTestResult(r),
    onError: (e: Error) =>
      toast({ title: "Test failed", description: e.message, variant: "destructive" }),
  });

  const handleContinue = async () => {
    if (apiKey) {
      await saveMut.mutateAsync();
    }
    onNext();
  };

  const RECOMMENDED_MODELS = [
    { value: "openai/gpt-4o", label: "GPT-4o — recommended" },
    { value: "openai/gpt-4o-mini", label: "GPT-4o mini — faster & cheaper" },
    { value: "anthropic/claude-sonnet-4", label: "Claude Sonnet 4" },
    { value: "google/gemma-3-27b-it:free", label: "Gemma 3 27B — free tier" },
  ];

  const ADVANCED_PROVIDERS = [
    { value: "openai", label: "OpenAI direct" },
    { value: "anthropic", label: "Anthropic direct" },
  ];

  return (
    <OnboardCard>
      <div className="flex flex-col gap-1">
        <span
          className="text-[#57f1db] text-[11px] tracking-[2px] uppercase"
          style={{ fontFamily: "Georgia, serif" }}
        >
          Step 2 of 3
        </span>
        <h2
          className="text-[28px] leading-[1.3] text-[#e1e2e4]"
          style={{ fontFamily: "Georgia, serif" }}
        >
          Connect your AI engine
        </h2>
        <p className="text-[#bacac5] text-sm">
          Leaka uses an AI model to operate your browser and execute tests. OpenRouter gives you access to every major model with one key.
        </p>
      </div>

      <div className="flex flex-col gap-4">
        {/* Provider — OpenRouter default */}
        <div
          className="rounded-xl p-4 flex items-start gap-3 cursor-pointer"
          style={{
            background: provider === "openrouter" ? "rgba(87,241,219,0.06)" : "rgba(29,32,33,0.4)",
            border: `1px solid ${provider === "openrouter" ? "rgba(87,241,219,0.25)" : "rgba(186,202,197,0.08)"}`,
          }}
          onClick={() => setProvider("openrouter")}
        >
          <div
            className="w-4 h-4 rounded-full mt-0.5 shrink-0 flex items-center justify-center"
            style={{ border: "2px solid #57f1db" }}
          >
            {provider === "openrouter" && (
              <span className="w-2 h-2 rounded-full bg-[#57f1db] block" />
            )}
          </div>
          <div>
            <p className="text-sm font-medium text-[#e1e2e4]">OpenRouter <span className="text-[#57f1db] text-xs ml-1">Recommended</span></p>
            <p className="text-xs text-[#bacac5] mt-0.5">One key. Every major model. Pay per use — pennies per test run.</p>
          </div>
        </div>

        {/* Model selector (OpenRouter only) */}
        {provider === "openrouter" && (
          <div>
            <Label className="text-[#bacac5] text-xs">Model</Label>
            <Select value={model} onValueChange={setModel}>
              <SelectTrigger className="mt-1 bg-[#1d2021] border-[rgba(186,202,197,0.12)] text-[#e1e2e4]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {RECOMMENDED_MODELS.map((m) => (
                  <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {/* API key */}
        <div>
          <Label className="text-[#bacac5] text-xs">
            {provider === "openrouter" ? "OpenRouter API key" : provider === "openai" ? "OpenAI API key" : "Anthropic API key"}
          </Label>
          <Input
            className="mt-1 font-mono bg-[#1d2021] border-[rgba(186,202,197,0.12)] text-[#e1e2e4]"
            type="password"
            placeholder={
              provider === "openrouter" ? "sk-or-v1-..."
              : provider === "openai" ? "sk-..."
              : "sk-ant-..."
            }
            value={apiKey}
            onChange={(e) => { setApiKey(e.target.value); setTestResult(null); }}
          />
          <p className="text-xs text-[#3c4a46] mt-1">
            {provider === "openrouter"
              ? "Get your key at openrouter.ai/keys"
              : provider === "openai"
              ? "Get your key at platform.openai.com/api-keys"
              : "Get your key at console.anthropic.com/settings/keys"}
          </p>
        </div>

        {/* Advanced toggle */}
        <button
          className="flex items-center gap-1.5 text-xs text-[#3c4a46] hover:text-[#bacac5] transition-colors w-fit"
          onClick={() => setShowAdvanced((v) => !v)}
        >
          {showAdvanced ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          Advanced — use a different provider
        </button>

        {showAdvanced && (
          <div className="flex gap-2">
            {ADVANCED_PROVIDERS.map((p) => (
              <button
                key={p.value}
                onClick={() => { setProvider(p.value); setApiKey(""); setTestResult(null); }}
                className="text-xs px-3 py-1.5 rounded-lg transition-colors"
                style={{
                  background: provider === p.value ? "rgba(87,241,219,0.08)" : "rgba(29,32,33,0.6)",
                  border: `1px solid ${provider === p.value ? "rgba(87,241,219,0.2)" : "rgba(186,202,197,0.08)"}`,
                  color: provider === p.value ? "#57f1db" : "#bacac5",
                }}
              >
                {p.label}
              </button>
            ))}
          </div>
        )}

        {/* Test result banner */}
        {testResult && (
          <div
            className={`rounded-lg p-3 text-sm ${
              testResult.ok
                ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-400"
                : "bg-red-500/10 border border-red-500/20 text-red-400"
            }`}
          >
            {testResult.ok ? "✅ " : "❌ "}{testResult.detail}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between">
        <SkipLink onSkip={onSkip} />
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            disabled={!apiKey || testMut.isPending}
            onClick={() => testMut.mutate()}
            className="border-[rgba(186,202,197,0.15)] text-[#bacac5] hover:text-[#e1e2e4]"
          >
            {testMut.isPending
              ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />Testing…</>
              : <><FlaskConical className="w-3.5 h-3.5 mr-1.5" />Test connection</>}
          </Button>
          <Button
            onClick={handleContinue}
            disabled={saveMut.isPending}
            className="gap-2 bg-[#57f1db] text-[#111415] hover:bg-[#57f1db]/90 font-semibold"
          >
            {saveMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            Continue <ArrowRight className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </OnboardCard>
  );
}

// ── Step 3 — Connect workflow ─────────────────────────────────────────────────
function StepConnectWorkflow({ onFinish }: { onFinish: () => void }) {
  const [slackUrl, setSlackUrl] = useState("");
  const [emailTo, setEmailTo] = useState("");
  const [linearKey, setLinearKey] = useState("");
  const [linearTeam, setLinearTeam] = useState("");
  const [connected, setConnected] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState<string | null>(null);

  const saveIntegration = async (key: string, payload: Parameters<typeof api.updateIntegrationSettings>[0]) => {
    setSaving(key);
    try {
      await api.updateIntegrationSettings(payload);
      setConnected((prev) => ({ ...prev, [key]: true }));
      toast({ title: `${key} connected` });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      toast({ title: `Failed to save ${key}`, description: msg, variant: "destructive" });
    } finally {
      setSaving(null);
    }
  };

  const integrations = [
    {
      key: "Slack",
      icon: <Bell className="w-5 h-5 text-[#57f1db]" />,
      title: "Slack",
      description: "Get QA failure alerts in your Slack channel instantly.",
      input: (
        <Input
          className="mt-1 font-mono bg-[#1d2021] border-[rgba(186,202,197,0.12)] text-[#e1e2e4] text-sm"
          placeholder="https://hooks.slack.com/services/…"
          value={slackUrl}
          onChange={(e) => setSlackUrl(e.target.value)}
        />
      ),
      canConnect: slackUrl.startsWith("https://hooks.slack.com/"),
      onConnect: () => saveIntegration("Slack", { slack_webhook_url: slackUrl }),
    },
    {
      key: "Email",
      icon: <Mail className="w-5 h-5 text-[#e3c0a0]" />,
      title: "Email alerts",
      description: "Receive failure reports with screenshots via email.",
      input: (
        <Input
          className="mt-1 bg-[#1d2021] border-[rgba(186,202,197,0.12)] text-[#e1e2e4] text-sm"
          placeholder="you@company.com"
          type="email"
          value={emailTo}
          onChange={(e) => setEmailTo(e.target.value)}
        />
      ),
      canConnect: emailTo.includes("@"),
      onConnect: () => saveIntegration("Email", { email_alert_to: emailTo }),
    },
    {
      key: "Linear",
      icon: <Ticket className="w-5 h-5 text-[#bacac5]" />,
      title: "Linear",
      description: "Auto-create engineering tickets when a test fails.",
      input: (
        <div className="flex flex-col gap-2 mt-1">
          <Input
            className="font-mono bg-[#1d2021] border-[rgba(186,202,197,0.12)] text-[#e1e2e4] text-sm"
            placeholder="lin_api_…"
            type="password"
            value={linearKey}
            onChange={(e) => setLinearKey(e.target.value)}
          />
          <Input
            className="font-mono bg-[#1d2021] border-[rgba(186,202,197,0.12)] text-[#e1e2e4] text-sm"
            placeholder="Team ID"
            value={linearTeam}
            onChange={(e) => setLinearTeam(e.target.value)}
          />
        </div>
      ),
      canConnect: linearKey.startsWith("lin_api_") && linearTeam.length > 4,
      onConnect: () => saveIntegration("Linear", { linear_api_key: linearKey, linear_team_id: linearTeam }),
    },
  ];

  return (
    <OnboardCard>
      <div className="flex flex-col gap-1">
        <span
          className="text-[#57f1db] text-[11px] tracking-[2px] uppercase"
          style={{ fontFamily: "Georgia, serif" }}
        >
          Step 3 of 3
        </span>
        <h2
          className="text-[28px] leading-[1.3] text-[#e1e2e4]"
          style={{ fontFamily: "Georgia, serif" }}
        >
          Connect your workflow
        </h2>
        <p className="text-[#bacac5] text-sm">
          These integrations are optional — you can add them now or any time from Settings.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {integrations.map((intg) => (
          <div
            key={intg.key}
            className="rounded-xl p-4 flex flex-col gap-3"
            style={{
              background: connected[intg.key] ? "rgba(87,241,219,0.04)" : "rgba(29,32,33,0.4)",
              border: `1px solid ${connected[intg.key] ? "rgba(87,241,219,0.15)" : "rgba(186,202,197,0.08)"}`,
            }}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                {intg.icon}
                <div>
                  <p className="text-sm font-medium text-[#e1e2e4]">{intg.title}</p>
                  <p className="text-xs text-[#bacac5]">{intg.description}</p>
                </div>
              </div>
              {connected[intg.key] && (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              )}
            </div>

            {!connected[intg.key] && (
              <div className="flex items-end gap-2">
                <div className="flex-1">{intg.input}</div>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!intg.canConnect || saving === intg.key}
                  onClick={intg.onConnect}
                  className="shrink-0 border-[rgba(186,202,197,0.15)] text-[#bacac5] hover:text-[#e1e2e4]"
                >
                  {saving === intg.key
                    ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    : "Connect"}
                </Button>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <SkipLink onSkip={onFinish} />
        <Button
          onClick={onFinish}
          className="gap-2 bg-[#57f1db] text-[#111415] hover:bg-[#57f1db]/90 font-semibold"
        >
          Go to dashboard <Sparkles className="w-4 h-4" />
        </Button>
      </div>
    </OnboardCard>
  );
}

// ── Main onboarding page ───────────────────────────────────────────────────────
export default function OnboardPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [step, setStep] = useState(0);
  const [redirecting, setRedirecting] = useState(true);

  // Check onboarding status — redirect to dashboard if already done
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
    // Not logged in — go to login
    if (!user) {
      router.replace("/login");
      return;
    }
    // Already onboarded — skip to dashboard
    if (onboardingData?.onboarding_completed) {
      router.replace("/dashboard");
      return;
    }
    setRedirecting(false);
  }, [authLoading, onboardingLoading, user, onboardingData, router]);

  const finish = async () => {
    // Mark as complete in DB and localStorage (fast-path for next visit)
    try {
      await completeMut.mutateAsync();
    } catch {
      // Non-blocking — even if this fails, we go to the dashboard
    }
    if (typeof window !== "undefined") {
      localStorage.setItem(ONBOARDING_KEY, "1");
    }
    router.replace("/dashboard");
  };

  // Show nothing while checking auth/onboarding state
  if (redirecting || authLoading || onboardingLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "#111415" }}>
        <Loader2 className="w-6 h-6 text-[#57f1db] animate-spin" />
      </div>
    );
  }

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center px-4 py-12"
      style={{ background: "#111415" }}
    >
      {/* Ambient glow */}
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage:
            "radial-gradient(ellipse 600px 400px at 60% 20%, rgba(45,212,191,0.06) 0%, transparent 70%)",
        }}
      />

      {/* Logo */}
      <div className="mb-8 flex flex-col items-center gap-2 relative z-10">
        <span
          className="text-[#e1e2e4] text-lg font-medium"
          style={{ fontFamily: "Georgia, serif" }}
        >
          Leaka AI
        </span>
        <StepDots current={step} />
      </div>

      {/* Step content */}
      <div className="relative z-10 w-full flex justify-center">
        {step === 0 && (
          <StepWelcome
            onNext={() => setStep(1)}
            onSkip={finish}
          />
        )}
        {step === 1 && (
          <StepConnectAI
            onNext={() => setStep(2)}
            onSkip={() => setStep(2)}
          />
        )}
        {step === 2 && (
          <StepConnectWorkflow
            onFinish={finish}
          />
        )}
      </div>
    </div>
  );
}
