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
import { Textarea } from "@/components/ui/textarea";
import {
  ArrowRight, Sparkles, Zap, Bell, Mail, Ticket,
  FlaskConical, Loader2, CheckCircle2, ChevronRight,
  ChevronDown, Check, ShieldCheck, Network, Database,
  Laptop, Key, Globe, RefreshCw, Lock, Shield, Layers
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
          className={`rounded-full transition-all duration-300 ${
            i === current
              ? "w-4 h-1.5 bg-[#57f1db]"
              : i < current
              ? "w-1.5 h-1.5 bg-[#57f1db]/50"
              : "w-1.5 h-1.5 bg-[#bacac5]/20"
          }`}
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
  const [model, setModel] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const handleNext = async () => {
    if (!apiKey) {
      onNext();
      return;
    }
    setIsSaving(true);
    try {
      await api.updateIntegrationSettings({
        llm_provider: provider,
        openrouter_api_key: provider === "openrouter" ? apiKey : undefined,
        openai_api_key: provider === "openai" ? apiKey : undefined,
        anthropic_api_key: provider === "anthropic" ? apiKey : undefined,
        llm_model_openrouter: provider === "openrouter" && model ? model : undefined,
      });
      onNext();
    } catch (e) {
      console.error("Failed to save LLM settings:", e);
      onNext(); // Proceed anyway, they can set it in Settings later
    } finally {
      setIsSaving(false);
    }
  };

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
        <div className="flex flex-col gap-2">
          <Label className="text-xs text-[#bacac5] uppercase tracking-wider">Model Override (Optional)</Label>
          <Input className="bg-[#111415] border-[rgba(186,202,197,0.12)] text-[#e1e2e4]" placeholder={provider === "openrouter" ? "e.g. openai/gpt-4o" : "Leave blank for default"} value={model} onChange={(e) => setModel(e.target.value)} />
        </div>
      </div>
      <div className="flex items-center justify-between mt-4">
        <SkipLink onSkip={onSkip} />
        <Button onClick={handleNext} disabled={isSaving} className="gap-2 bg-[#e1e2e4] text-[#111415] hover:bg-white font-semibold">
          {isSaving ? "Saving..." : "Next"} <ArrowRight className="w-4 h-4" />
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
        <p className="text-[#bacac5] text-sm">Create your application profile before we connect the AI to it.</p>
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
        <Button disabled={!name || !url || isLoading} onClick={handleNext} className="gap-2 bg-[#e1e2e4] text-[#111415] hover:bg-white font-semibold">
          {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Next <ArrowRight className="w-4 h-4" /></>}
        </Button>
      </div>
    </OnboardCard>
  );
}

// -- STEP 3: Authentication / Auth Strategy --
function StepAuthWallet({ onNext, onSkip, appId, envId }: { onNext: () => void; onSkip: () => void; appId: number | null; envId: number | null; }) {
  const [authMode, setAuthMode] = useState<"extension" | "visual" | "public" | "api">("extension");

  // Tier 2: Visual Login fields
  const [visualUser, setVisualUser] = useState("");
  const [visualPass, setVisualPass] = useState("");
  const [visualUrl, setVisualUrl] = useState("");

  // Advanced: Direct API fields
  const [apiUrl, setApiUrl] = useState("");
  const [headers, setHeaders] = useState("");
  const [payload, setPayload] = useState("{\n  \"email\": \"test@acme.com\",\n  \"password\": \"password123\"\n}");
  const [tokenPath, setTokenPath] = useState("access_token");
  const [injectionTarget, setInjectionTarget] = useState("localStorage");
  const [injectionKey, setInjectionKey] = useState("sb-xxxx-auth-token");
  const [injectionDomain, setInjectionDomain] = useState("");

  const [isLoading, setIsLoading] = useState(false);

  // Poll environment every 2.5s to detect if user pushed session state from the Extension
  const { data: envs, refetch: refetchEnvs } = useQuery({
    queryKey: ["onboard-env-check", appId],
    queryFn: () => (appId ? api.listEnvironments(appId) : null),
    enabled: !!appId,
    refetchInterval: 2500,
  });

  const activeEnv = envs?.find((e) => e.id === envId) || envs?.[0];
  const hasExtensionSession = activeEnv?.auth_strategy === "state_cache" && !!activeEnv?.auth_state_template;

  let sessionCountInfo = "";
  if (hasExtensionSession && activeEnv?.auth_state_template) {
    try {
      const parsed = JSON.parse(activeEnv.auth_state_template);
      const cookies = parsed.cookies?.length || 0;
      const ls = parsed.origins?.[0]?.localStorage?.length || 0;
      sessionCountInfo = `${cookies} cookies & ${ls} storage items ready`;
    } catch {
      sessionCountInfo = "Active browser session injected";
    }
  }

  const handleNextWithExtension = async () => {
    if (!appId) return handleSkip();
    setIsLoading(true);
    try {
      await api.exploreApplication(appId, 40, envId ?? undefined);
      onNext();
    } catch (e) {
      toast({ title: "Error starting exploration" });
    } finally {
      setIsLoading(false);
    }
  };

  const handleNextWithVisual = async () => {
    if (!appId || !envId) return handleSkip();
    setIsLoading(true);
    try {
      await api.updateEnvironment(appId, envId, {
        auth_strategy: "visual_login",
        auth_payload: JSON.stringify({
          login_url: visualUrl || undefined,
          username: visualUser,
          password: visualPass,
        }),
      });
      await api.exploreApplication(appId, 40, envId);
      onNext();
    } catch (e) {
      toast({ title: "Error saving credentials" });
    } finally {
      setIsLoading(false);
    }
  };

  const handleNextWithApi = async () => {
    if (!apiUrl || !appId || !envId) return handleSkip();
    setIsLoading(true);

    let stateTemplate = "";
    const cleanDomain = injectionDomain.replace(/^(https?:\/\/)/, "").replace(/\/$/, "");
    if (injectionTarget === "localStorage") {
      stateTemplate = JSON.stringify({
        cookies: [],
        origins: [{
          origin: `https://${cleanDomain}`,
          localStorage: [{
            name: injectionKey,
            value: "{{token}}"
          }]
        }]
      }, null, 2);
    } else {
      stateTemplate = JSON.stringify({
        cookies: [{
          name: injectionKey,
          value: "{{token}}",
          domain: cleanDomain,
          path: "/",
          httpOnly: false,
          secure: true,
          sameSite: "Lax"
        }],
        origins: []
      }, null, 2);
    }

    try {
      await api.updateEnvironment(appId, envId, {
        auth_strategy: "api_injection",
        auth_api_url: apiUrl,
        auth_api_headers: headers || undefined,
        auth_payload: payload,
        auth_token_path: tokenPath,
        auth_state_template: stateTemplate,
      });
      await api.exploreApplication(appId, 40, envId);
      onNext();
    } catch (e) {
      toast({ title: "Error saving Auth Wallet" });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSkip = async () => {
    if (appId) {
      await api.exploreApplication(appId, 40);
    }
    onSkip();
  };

  return (
    <OnboardCard>
      <div className="flex flex-col gap-1">
        <span className="text-[#57f1db] text-[11px] tracking-[2px] uppercase" style={{ fontFamily: "Georgia, serif" }}>Step 3 of 5</span>
        <h2 className="text-[28px] leading-[1.3] text-[#e1e2e4]" style={{ fontFamily: "Georgia, serif" }}>Connect Authentication</h2>
        <p className="text-[#bacac5] text-sm">Choose how Leaka accesses protected pages during automated tests.</p>
      </div>

      {/* Mode Selector Tabs */}
      <div className="grid grid-cols-3 gap-1.5 p-1 bg-[#111415] rounded-lg border border-[rgba(186,202,197,0.1)]">
        <button
          type="button"
          onClick={() => setAuthMode("extension")}
          className={`flex items-center justify-center gap-1.5 py-2 px-2 rounded-md text-xs font-medium transition-all ${
            authMode === "extension" ? "bg-[#1d2021] text-[#57f1db] shadow" : "text-[#bacac5] hover:text-white"
          }`}
        >
          <Laptop className="w-3.5 h-3.5" />
          <span>Extension</span>
        </button>
        <button
          type="button"
          onClick={() => setAuthMode("visual")}
          className={`flex items-center justify-center gap-1.5 py-2 px-2 rounded-md text-xs font-medium transition-all ${
            authMode === "visual" ? "bg-[#1d2021] text-[#57f1db] shadow" : "text-[#bacac5] hover:text-white"
          }`}
        >
          <Key className="w-3.5 h-3.5" />
          <span>Login Form</span>
        </button>
        <button
          type="button"
          onClick={() => setAuthMode("public")}
          className={`flex items-center justify-center gap-1.5 py-2 px-2 rounded-md text-xs font-medium transition-all ${
            authMode === "public" ? "bg-[#1d2021] text-[#57f1db] shadow" : "text-[#bacac5] hover:text-white"
          }`}
        >
          <Globe className="w-3.5 h-3.5" />
          <span>Public / Skip</span>
        </button>
      </div>

      {/* Tab 1: Extension Session Sync */}
      {authMode === "extension" && (
        <div className="flex flex-col gap-3">
          {hasExtensionSession ? (
            <div className="p-4 rounded-lg bg-[#57f1db]/10 border border-[#57f1db]/30 flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-[#57f1db]" />
                <span className="text-sm font-semibold text-[#57f1db]">Active Browser Session Synced!</span>
              </div>
              <p className="text-xs text-[#e1e2e4]/80">
                {sessionCountInfo}. The headless browser will start already authenticated into your product.
              </p>
            </div>
          ) : (
            <div className="p-3.5 rounded-lg bg-[#16191a] border border-[rgba(186,202,197,0.12)] flex flex-col gap-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-[#e1e2e4]">1-Click Active Session Capture</span>
                <span className="text-[10px] text-[#57f1db] bg-[#57f1db]/10 px-2 py-0.5 rounded font-mono">Recommended</span>
              </div>
              <p className="text-xs text-[#bacac5] leading-relaxed">
                Already logged in via Google, GitHub, or email? Push your current session to Leaka without sharing passwords:
              </p>
              <ol className="text-xs text-[#e1e2e4]/90 list-decimal list-inside space-y-1.5 pl-1">
                <li>Open your product in Chrome where you are logged in.</li>
                <li>Click the Leaka extension and hit <span className="text-[#57f1db] font-medium">&quot;Push State to Environment&quot;</span>.</li>
                <li>This card automatically detects your session.</li>
              </ol>
              <Button
                variant="outline"
                size="sm"
                onClick={() => refetchEnvs()}
                className="mt-1 gap-2 border-[rgba(186,202,197,0.2)] text-[#bacac5] hover:text-white text-xs h-8"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Check Sync Status
              </Button>
            </div>
          )}

          <div className="flex items-center justify-between mt-2">
            <SkipLink onSkip={handleSkip} />
            <Button
              disabled={isLoading}
              onClick={handleNextWithExtension}
              className="gap-2 bg-[#57f1db] text-[#111415] hover:bg-[#57f1db]/90 font-semibold"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Start Mapping <Zap className="w-4 h-4" /></>}
            </Button>
          </div>
        </div>
      )}

      {/* Tab 2: Visual Login Form */}
      {authMode === "visual" && (
        <div className="flex flex-col gap-3">
          <div className="p-3.5 rounded-lg bg-[#16191a] border border-[rgba(186,202,197,0.12)] flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-[#e1e2e4]">AI Visual Login</span>
              <p className="text-[11px] text-[#bacac5]">
                Leaka will navigate to your login form, enter credentials, and log in visually.
              </p>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-[10px] text-[#bacac5] uppercase">Login Page URL (Optional)</Label>
              <Input
                className="bg-[#111415] border-[rgba(186,202,197,0.12)] text-[#e1e2e4] h-8 text-xs"
                placeholder="https://staging.acme.com/login"
                value={visualUrl}
                onChange={(e) => setVisualUrl(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-[10px] text-[#bacac5] uppercase">Test Email / Username</Label>
              <Input
                className="bg-[#111415] border-[rgba(186,202,197,0.12)] text-[#e1e2e4] h-8 text-xs"
                placeholder="testuser@acme.com or you+test@gmail.com"
                value={visualUser}
                onChange={(e) => setVisualUser(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-[10px] text-[#bacac5] uppercase">Password</Label>
              <Input
                type="password"
                className="bg-[#111415] border-[rgba(186,202,197,0.12)] text-[#e1e2e4] h-8 text-xs"
                placeholder="••••••••••••"
                value={visualPass}
                onChange={(e) => setVisualPass(e.target.value)}
              />
            </div>
          </div>

          <div className="flex items-center justify-between mt-2">
            <SkipLink onSkip={handleSkip} />
            <Button
              disabled={isLoading || !visualUser || !visualPass}
              onClick={handleNextWithVisual}
              className="gap-2 bg-[#57f1db] text-[#111415] hover:bg-[#57f1db]/90 font-semibold"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Save & Map <Zap className="w-4 h-4" /></>}
            </Button>
          </div>
        </div>
      )}

      {/* Tab 3: Public / Skip */}
      {authMode === "public" && (
        <div className="flex flex-col gap-3">
          <div className="p-4 rounded-lg bg-[#16191a] border border-[rgba(186,202,197,0.12)] flex flex-col gap-2">
            <span className="text-xs font-semibold text-[#e1e2e4]">Public Testing Mode</span>
            <p className="text-xs text-[#bacac5] leading-relaxed">
              No login required. Leaka will crawl and test your public landing pages, pricing calculators, docs, or registration forms.
            </p>
          </div>

          <div className="flex items-center justify-between mt-2">
            <SkipLink onSkip={handleSkip} />
            <Button
              disabled={isLoading}
              onClick={handleSkip}
              className="gap-2 bg-[#57f1db] text-[#111415] hover:bg-[#57f1db]/90 font-semibold"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Continue to Mapping <ArrowRight className="w-4 h-4" /></>}
            </Button>
          </div>
        </div>
      )}

      {/* Collapsible Advanced Section for direct API injection */}
      <div className="pt-2 border-t border-[rgba(186,202,197,0.08)]">
        <button
          type="button"
          onClick={() => setAuthMode(authMode === "api" ? "extension" : "api")}
          className="text-[11px] text-[#bacac5]/70 hover:text-[#57f1db] flex items-center gap-1 transition-colors"
        >
          {authMode === "api" ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          <span>Advanced: Direct API Token Injection</span>
        </button>

        {authMode === "api" && (
          <div className="flex flex-col gap-3 mt-3 max-h-[300px] overflow-y-auto pr-1">
            <div className="p-3 border border-[rgba(186,202,197,0.12)] rounded-md bg-[#16191a] flex flex-col gap-2.5">
              <div className="flex flex-col gap-1.5">
                <Label className="text-[10px] text-[#bacac5] uppercase">API Login Endpoint</Label>
                <Input className="bg-[#111415] border-[rgba(186,202,197,0.12)] text-[#e1e2e4] h-7 text-xs" placeholder="https://api.acme.com/v1/login" value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="text-[10px] text-[#bacac5] uppercase">Headers (JSON)</Label>
                <Textarea className="bg-[#111415] border-[rgba(186,202,197,0.12)] text-[#e1e2e4] font-mono text-[10px] min-h-[50px]" placeholder='{"apikey": "..."}' value={headers} onChange={(e) => setHeaders(e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="text-[10px] text-[#bacac5] uppercase">JSON Payload</Label>
                <Textarea className="bg-[#111415] border-[rgba(186,202,197,0.12)] text-[#e1e2e4] font-mono text-[10px] min-h-[60px]" value={payload} onChange={(e) => setPayload(e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="text-[10px] text-[#bacac5] uppercase">JSON Path to Token</Label>
                <Input className="bg-[#111415] border-[rgba(186,202,197,0.12)] text-[#e1e2e4] font-mono h-7 text-xs" placeholder="data.access_token" value={tokenPath} onChange={(e) => setTokenPath(e.target.value)} />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="flex flex-col gap-1">
                  <Label className="text-[10px] text-[#bacac5] uppercase">Target</Label>
                  <Select value={injectionTarget} onValueChange={setInjectionTarget}>
                    <SelectTrigger className="bg-[#111415] border-[rgba(186,202,197,0.12)] text-[#e1e2e4] h-7 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-[#1d2021] border-[rgba(186,202,197,0.12)] text-[#e1e2e4]">
                      <SelectItem value="localStorage">LocalStorage</SelectItem>
                      <SelectItem value="cookie">Cookie</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-[10px] text-[#bacac5] uppercase">Key Name</Label>
                  <Input className="bg-[#111415] border-[rgba(186,202,197,0.12)] text-[#e1e2e4] font-mono h-7 text-xs" placeholder="sb-...-auth-token" value={injectionKey} onChange={(e) => setInjectionKey(e.target.value)} />
                </div>
              </div>
            </div>

            <Button
              disabled={isLoading || !apiUrl}
              onClick={handleNextWithApi}
              className="gap-2 bg-[#57f1db] text-[#111415] hover:bg-[#57f1db]/90 font-semibold"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Save & Map with API <Zap className="w-4 h-4" /></>}
            </Button>
          </div>
        )}
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
          <Textarea className="bg-[#111415] border-[rgba(186,202,197,0.12)] text-[#e1e2e4] font-mono text-xs h-32" placeholder={"{ \"openapi\": \"3.0.0\", ... }"} value={spec} onChange={(e) => setSpec(e.target.value)} />
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
function StepAhaMoment({ onFinish, appId, envId }: { onFinish: () => void; appId: number | null; envId: number | null; }) {
  const { data: graphData } = useQuery({
    queryKey: ["app-graph", appId],
    queryFn: () => appId ? api.getApplicationGraph(appId) : null,
    enabled: !!appId,
    refetchInterval: 3000,
  });

  const nodeCount = graphData?.nodes?.length || 0;
  const nodes = graphData?.nodes || [];

  return (
    <OnboardCard>
      <div className="flex flex-col items-center justify-center text-center gap-4 py-4">
        <div className="h-16 w-16 bg-[#57f1db]/10 rounded-full flex items-center justify-center mb-2">
          <Network className="w-8 h-8 text-[#57f1db]" />
        </div>
        <h2 className="text-[28px] leading-[1.3] text-[#e1e2e4]" style={{ fontFamily: "Georgia, serif" }}>
          {nodeCount > 0 ? "Leaka has mapped your app." : "Mapping In Progress"}
        </h2>
        <p className="text-[#bacac5] text-sm">
          {nodeCount > 0 ? (
            <>Autonomous agent identified <span className="text-white font-bold">{nodeCount}</span> functional nodes in your application.</>
          ) : (
            <>The autonomous crawler is exploring your application in the background. You can start running automated tests right away.</>
          )}
        </p>

        <div className="w-full bg-[#111415] border border-[rgba(186,202,197,0.12)] rounded-lg p-4 mt-2 text-left">
          <p className="text-xs text-[#bacac5] uppercase tracking-wider mb-3">
            {nodeCount > 0 ? "Discovered Application Nodes" : "Initial Verification Suite"}
          </p>
          <div className="flex flex-col gap-2">
            {nodeCount > 0 ? (
              nodes.slice(0, 4).map((n: any, idx: number) => (
                <div key={n.id || idx} className="flex items-center justify-between p-2 bg-[#1d2021] rounded border border-[rgba(186,202,197,0.08)]">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-[#57f1db]" />
                    <span className="text-sm text-[#e1e2e4] font-medium">{n.label || n.url || "Discovered Page"}</span>
                  </div>
                  <span className="text-[10px] text-[#57f1db] uppercase px-1.5 py-0.5 rounded bg-[#57f1db]/10 font-mono">
                    {n.node_type || "page"}
                  </span>
                </div>
              ))
            ) : (
              <>
                <div className="flex items-center gap-2 p-2 bg-[#1d2021] rounded border border-[rgba(186,202,197,0.08)]">
                  <CheckCircle2 className="w-4 h-4 text-[#57f1db]" />
                  <span className="text-sm text-[#e1e2e4]">Initial Site Health Check (Auto-dispatched)</span>
                </div>
                <div className="flex items-center gap-2 p-2 bg-[#1d2021] rounded border border-[rgba(186,202,197,0.08)]">
                  <CheckCircle2 className="w-4 h-4 text-[#57f1db]" />
                  <span className="text-sm text-[#e1e2e4]">Landing & Navigation Integrity Check</span>
                </div>
              </>
            )}
          </div>
        </div>

      </div>
      <div className="flex items-center justify-center mt-2">
        <Button onClick={onFinish} className="gap-2 w-full bg-[#57f1db] text-[#111415] hover:bg-[#57f1db]/90 font-semibold">
          Launch Health Check & View Dashboard <Sparkles className="w-4 h-4" />
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
    try {
      if (envId) {
        toast({ title: "Launching Initial Smoke Test", description: "Running automated site health verification..." });
        await api.enqueueRun({
          name: "Initial Site Health Check",
          prompt: "Navigate to the site. Verify the page loads cleanly with no HTTP 500 errors or visible broken UI. Confirm that the main navigation and primary CTA buttons are visible.",
          environment_id: envId,
          use_vision: true,
          max_steps: 10,
        });
      }
    } catch (e) {
      console.warn("Auto smoke test enqueue:", e);
    }
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
        {step === 4 && <StepAhaMoment onFinish={finish} appId={appId} envId={envId} />}
      </div>
    </div>
  );
}
