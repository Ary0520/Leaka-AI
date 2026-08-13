"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, CheckCircle2, ChevronDown, Pencil, Mail, Aperture, Asterisk, Cpu, Github, Settings2, Copy, RefreshCcw } from "lucide-react";
import { toast } from "@/components/ui/use-toast";
import { cn } from "@/lib/utils";
import Link from "next/link";

// ── LOGOS ──

const SlackLogo = () => (
  <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5">
    <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52z" fill="#E01E5A"/>
    <path d="M6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z" fill="#E01E5A"/>
    <path d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834z" fill="#36C5F0"/>
    <path d="M8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z" fill="#36C5F0"/>
    <path d="M18.956 8.835a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.835a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.835z" fill="#2EB67D"/>
    <path d="M17.687 8.835a2.528 2.528 0 0 1-2.521 2.521 2.528 2.528 0 0 1-2.522-2.521V2.522A2.528 2.528 0 0 1 15.166 0a2.528 2.528 0 0 1 2.521 2.522v6.313z" fill="#2EB67D"/>
    <path d="M15.166 18.958a2.528 2.528 0 0 1 2.521 2.522A2.528 2.528 0 0 1 15.166 24a2.528 2.528 0 0 1-2.521-2.522v-2.52h2.521z" fill="#ECB22E"/>
    <path d="M15.166 17.687a2.528 2.528 0 0 1-2.521-2.521 2.528 2.528 0 0 1 2.521-2.522h6.312A2.528 2.528 0 0 1 24 15.166a2.528 2.528 0 0 1-2.522 2.521h-6.312z" fill="#ECB22E"/>
  </svg>
);

const LinearLogo = () => (
  <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5">
    <path d="M12.98 23.36V.636C12.98.285 12.68 0 12.32 0c-.08 0-.16.016-.24.047L2.43 3.966c-.28.112-.46.384-.46.687v14.694c0 .272.15.518.39.637l9.65 4.825c.31.155.68-.057.68-.405z" fill="#fff"/>
    <path d="M13.68.047A.706.706 0 0 0 13.44 0c-.36 0-.66.285-.66.636v22.728c0 .348.37.56.68.405l9.65-4.825a.706.706 0 0 0 .39-.637V4.653c0-.303-.18-.575-.46-.687L13.68.047z" fill="#fff" opacity="0.6"/>
  </svg>
);

const ResendLogo = () => (
  <Mail className="w-5 h-5 text-white" />
);

// ── REUSABLE COMPONENTS ──

function MaskedCredentialField({ 
  label, value, onChange, placeholder, onSave, isSaving, isSet, isMaskedFallback = "••••••••••••••••"
}: { 
  label: string; value: string; onChange: (val: string) => void; placeholder: string; onSave: () => void; isSaving: boolean; isSet: boolean; isMaskedFallback?: string;
}) {
  const [isEditing, setIsEditing] = useState(false);

  return (
    <div className="space-y-2">
      <Label className="text-[10px] tracking-widest font-semibold uppercase text-muted-foreground">{label}</Label>
      {isEditing || !isSet ? (
        <div className="flex items-center gap-2">
           <Input 
             type="text" 
             className="font-mono bg-[#0B0E14] border-transparent h-10 text-sm focus-visible:ring-1 focus-visible:ring-indigo-500/50" 
             value={value} 
             onChange={e => onChange(e.target.value)} 
             placeholder={placeholder} 
             autoFocus={isEditing} 
           />
           <Button size="sm" onClick={() => { onSave(); setIsEditing(false); }} disabled={isSaving} className="bg-indigo-300 text-indigo-950 hover:bg-indigo-400 font-semibold px-4 h-10">
             {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Save"}
           </Button>
           {isEditing && isSet && (
             <Button size="sm" variant="ghost" className="h-10 text-muted-foreground" onClick={() => setIsEditing(false)}>Cancel</Button>
           )}
        </div>
      ) : (
        <div className="flex items-center gap-2">
           <div className="h-10 flex items-center px-4 rounded-md bg-[#0B0E14] border border-transparent font-mono text-sm text-muted-foreground/70 w-full truncate">
             {isMaskedFallback}
           </div>
           <Button size="icon" variant="ghost" className="h-10 w-10 shrink-0 text-muted-foreground hover:text-white bg-[#161922] border-transparent" onClick={() => setIsEditing(true)}>
             <Pencil className="w-4 h-4" />
           </Button>
        </div>
      )}
    </div>
  )
}

function IntegrationCard({
  name, description, logo, logoBgClass, isConnected, statusCaption, isRequired, emptyStateText, onDisconnect, children
}: {
  name: string; description: string; logo: React.ReactNode; logoBgClass: string; isConnected: boolean; statusCaption?: string; isRequired?: boolean; emptyStateText?: string; onDisconnect?: () => void; children: React.ReactNode;
}) {
  const [isExpanded, setIsExpanded] = useState(isRequired || isConnected);
  const expanded = isRequired ? true : isExpanded;

  return (
    <Card className={cn(
      "border-0 overflow-hidden transition-all duration-300",
      isConnected 
        ? "bg-[#161922] shadow-[0_-1px_10px_rgba(34,197,94,0.05)] border-t border-t-emerald-500/30" 
        : "bg-[#161922]/50 border border-muted/10"
    )}>
      <div 
        className={cn("p-5 flex items-center justify-between", (!expanded || !isRequired) && "cursor-pointer select-none")}
        onClick={() => !isRequired && setIsExpanded(!expanded)}
      >
        <div className="flex items-center gap-4">
          <div className={cn("w-10 h-10 rounded-xl grid place-items-center shadow-sm shrink-0", logoBgClass, !isConnected && "opacity-70 saturate-50")}>
            {logo}
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h3 className="font-medium text-foreground text-sm">{name}</h3>
              {isConnected ? (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500 text-[10px] uppercase tracking-wider font-bold">
                  <CheckCircle2 className="w-3 h-3" /> Connected
                </span>
              ) : (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-muted/50 text-muted-foreground text-[10px] uppercase tracking-wider font-semibold">
                  Not connected
                </span>
              )}
            </div>
            <p className="text-sm text-muted-foreground mt-0.5 leading-tight">
              {isConnected && statusCaption ? statusCaption : description}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {isConnected && onDisconnect && !isRequired && (
             <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-destructive h-8 text-xs font-medium" onClick={(e) => { e.stopPropagation(); onDisconnect(); }}>
               Disconnect
             </Button>
          )}
          {!isRequired && (
            <ChevronDown className={cn("w-4 h-4 text-muted-foreground transition-transform duration-200", expanded && "rotate-180")} />
          )}
        </div>
      </div>
      
      {expanded && (
        <div className="px-5 pb-5 pt-3 border-t border-border/30">
          {!isConnected && emptyStateText && (
            <p className="text-sm text-muted-foreground mb-5 max-w-2xl">{emptyStateText}</p>
          )}
          {children}
        </div>
      )}
    </Card>
  )
}

// ── MAIN PAGE COMPONENT ──

export default function SettingsPage() {
  const qc = useQueryClient();
  
  const { data, isLoading } = useQuery({
    queryKey: ["integration-settings"],
    queryFn: () => api.getIntegrationSettings(),
  });

  const { data: slackData, isLoading: slackLoading } = useQuery({
    queryKey: ["user-slack-settings"],
    queryFn: () => api.getUserSlackSettings(),
  });

  // Local form state
  const [linearKey, setLinearKey] = useState("");
  const [linearTeam, setLinearTeam] = useState("");
  const [resendKey, setResendKey] = useState("");
  const [emailFrom, setEmailFrom] = useState("");
  const [emailTo, setEmailTo] = useState("");
  
  const [slackWebhookUrl, setSlackWebhookUrl] = useState("");
  const [slackAutoAlert, setSlackAutoAlert] = useState(true);
  const [slackDashboardUrl, setSlackDashboardUrl] = useState("");

  const [llmProvider, setLlmProvider] = useState("");
  const [openrouterKey, setOpenrouterKey] = useState("");
  const [openrouterModel, setOpenrouterModel] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [anthropicKey, setAnthropicKey] = useState("");
  
  const [ciToken, setCiToken] = useState("");
  
  const [llmTestResult, setLlmTestResult] = useState<{ ok: boolean; provider: string; model: string; detail: string } | null>(null);

  // Initial population
  useEffect(() => {
    if (data) {
      setLinearTeam(data.linear.team_id ?? "");
      setEmailFrom(data.resend.email_from ?? "");
      setEmailTo(data.resend.email_alert_to ?? "");
      setLlmProvider(data.llm.provider ?? "");
      setOpenrouterModel(data.llm.openrouter_model ?? "");
      setCiToken(data.ci.webhook_token ?? "");
    }
  }, [data]);

  useEffect(() => {
    if (slackData) {
      setSlackAutoAlert(slackData.slack_auto_alert_on_failure);
      setSlackDashboardUrl(slackData.dashboard_base_url ?? "");
    }
  }, [slackData]);

  // Mutations
  const saveMut = useMutation({
    mutationFn: (payload: Parameters<typeof api.updateIntegrationSettings>[0]) =>
      api.updateIntegrationSettings(payload),
    onSuccess: () => {
      toast({ title: "Settings saved" });
      qc.invalidateQueries({ queryKey: ["integration-settings"] });
    },
    onError: (e: Error) => toast({ title: "Save failed", description: e.message, variant: "destructive" }),
  });

  const saveSlackMut = useMutation({
    mutationFn: () =>
      api.updateUserSlackSettings({
        slack_webhook_url: slackWebhookUrl || undefined,
        slack_auto_alert_on_failure: slackAutoAlert,
        dashboard_base_url: slackDashboardUrl || undefined,
      }),
    onSuccess: () => {
      toast({ title: "Slack settings saved" });
      setSlackWebhookUrl("");
      qc.invalidateQueries({ queryKey: ["user-slack-settings"] });
    },
    onError: (e: Error) => toast({ title: "Save failed", description: e.message, variant: "destructive" }),
  });

  const testSlackMut = useMutation({
    mutationFn: () => api.testSlackPing(),
    onSuccess: (r) => {
      toast({
        title: r.ok ? "Ping sent ✓" : "Ping failed",
        description: r.message,
        variant: r.ok ? "default" : "destructive",
      });
    },
    onError: (e: Error) => toast({ title: "Ping failed", description: e.message, variant: "destructive" }),
  });

  const testLlmMut = useMutation({
    mutationFn: () => api.testLlmConnection(),
    onSuccess: (r) => {
      setLlmTestResult(r);
      toast({
        title: r.ok ? "LLM connection verified ✓" : "LLM connection failed",
        description: r.detail,
        variant: r.ok ? "default" : "destructive",
      });
    },
    onError: (e: Error) => toast({ title: "Connection test failed", description: e.message, variant: "destructive" }),
  });

  const copyToClip = (text: string) => {
    navigator.clipboard.writeText(text);
    toast({ title: "Copied to clipboard" });
  };

  if (isLoading || slackLoading) {
    return <div className="max-w-3xl space-y-4 animate-pulse"><div className="h-40 bg-[#161922] rounded-xl border border-muted/10"></div><div className="h-40 bg-[#161922] rounded-xl border border-muted/10"></div></div>;
  }

  // Count active integrations
  const isLlmSet = data?.llm.openrouter_key_set || data?.llm.openai_key_set || data?.llm.anthropic_key_set || llmProvider === "ollama";
  const activeCount = [
    isLlmSet,
    slackData?.slack_webhook_url_set,
    data?.resend.api_key_set,
    data?.linear.api_key_set,
    data?.ci.webhook_token
  ].filter(Boolean).length;

  return (
    <div className="max-w-3xl space-y-10 pb-12">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground flex items-center gap-2">
            <Settings2 className="w-6 h-6 text-indigo-400" /> Integrations
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Connect the tools Leaka alerts and reports bugs to. Changes apply immediately.
          </p>
        </div>
        <div className="bg-[#161922] border border-muted/20 text-muted-foreground font-mono text-xs px-3 py-1.5 rounded-full font-medium shadow-sm">
          {activeCount} of 5 connected
        </div>
      </div>

      {/* ── AI ENGINE ── */}
      <div className="space-y-3">
        <div className="text-[10px] tracking-widest uppercase font-semibold text-muted-foreground pl-1">AI Engine</div>
        <IntegrationCard
          name="AI Provider"
          description="The language model that drives the browser-use agent."
          logo={<Cpu className="w-5 h-5 text-white" />}
          logoBgClass="bg-[#2D2D2D]"
          isConnected={!!isLlmSet}
          statusCaption={llmTestResult ? `Last tested: ${llmTestResult.ok ? 'successful' : 'failed'}` : "Required core integration"}
          isRequired
        >
          <div className="space-y-6">
            <div className="space-y-2">
              <Label className="text-[10px] tracking-widest font-semibold uppercase text-muted-foreground">Select Provider</Label>
              <Select value={llmProvider} onValueChange={(v) => { setLlmProvider(v); setLlmTestResult(null); }}>
                <SelectTrigger className="w-full bg-[#0B0E14] border-transparent font-mono text-sm h-11 text-foreground focus:ring-1 focus:ring-indigo-500/50">
                  <SelectValue placeholder="Choose provider" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="openrouter"><div className="flex items-center gap-2"><Cpu className="w-3.5 h-3.5 text-muted-foreground" /> OpenRouter</div></SelectItem>
                  <SelectItem value="openai"><div className="flex items-center gap-2"><Aperture className="w-3.5 h-3.5 text-muted-foreground" /> OpenAI</div></SelectItem>
                  <SelectItem value="anthropic"><div className="flex items-center gap-2"><Asterisk className="w-3.5 h-3.5 text-muted-foreground" /> Anthropic</div></SelectItem>
                  <SelectItem value="ollama"><div className="flex items-center gap-2"><Cpu className="w-3.5 h-3.5 text-muted-foreground" /> Ollama</div></SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            {llmProvider === "openrouter" && (
              <>
                <MaskedCredentialField 
                  label="OpenRouter API Key" 
                  placeholder="sk-or-v1-..." 
                  value={openrouterKey} 
                  onChange={setOpenrouterKey} 
                  isSet={data?.llm.openrouter_key_set ?? false} 
                  isMaskedFallback="sk-or-v1-••••••••••••••••"
                  isSaving={saveMut.isPending}
                  onSave={() => saveMut.mutate({ llm_provider: "openrouter", openrouter_api_key: openrouterKey || undefined })} 
                />
                <div className="space-y-2 pt-2">
                  <Label className="text-[10px] tracking-widest font-semibold uppercase text-muted-foreground">Model Override</Label>
                  <Input className="font-mono bg-[#0B0E14] border-transparent h-10 text-sm focus-visible:ring-1 focus-visible:ring-indigo-500/50" placeholder="openai/gpt-4o-mini" value={openrouterModel} onChange={e => setOpenrouterModel(e.target.value)} />
                </div>
              </>
            )}
            
            {llmProvider === "openai" && (
               <MaskedCredentialField 
                 label="OpenAI API Key" 
                 placeholder="sk-..." 
                 value={openaiKey} 
                 onChange={setOpenaiKey} 
                 isSet={data?.llm.openai_key_set ?? false} 
                 isMaskedFallback="sk-••••••••••••••••"
                 isSaving={saveMut.isPending}
                 onSave={() => saveMut.mutate({ llm_provider: "openai", openai_api_key: openaiKey || undefined })} 
               />
            )}
            
            {llmProvider === "anthropic" && (
               <MaskedCredentialField 
                 label="Anthropic API Key" 
                 placeholder="sk-ant-..." 
                 value={anthropicKey} 
                 onChange={setAnthropicKey} 
                 isSet={data?.llm.anthropic_key_set ?? false} 
                 isMaskedFallback="sk-ant-••••••••••••••••"
                 isSaving={saveMut.isPending}
                 onSave={() => saveMut.mutate({ llm_provider: "anthropic", anthropic_api_key: anthropicKey || undefined })} 
               />
            )}
            
            {llmProvider === "ollama" && (
               <div className="p-4 bg-[#0B0E14] rounded-md border border-muted/10 text-muted-foreground text-sm flex items-start gap-3">
                 <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1.5 shrink-0" />
                 Ollama runs locally. No API key needed. Ensure Ollama is running on port 11434 before testing the connection.
               </div>
            )}

            <div className="flex items-center gap-4 pt-4 border-t border-border/20 mt-6">
              <Button onClick={() => saveMut.mutate({ llm_provider: llmProvider, llm_model_openrouter: openrouterModel || undefined, openrouter_api_key: openrouterKey || undefined, openai_api_key: openaiKey || undefined, anthropic_api_key: anthropicKey || undefined })} disabled={saveMut.isPending} className="bg-indigo-300 text-indigo-950 hover:bg-indigo-400 font-semibold h-9 px-5">
                {saveMut.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : "Save LLM settings"}
              </Button>
              <Button variant="ghost" onClick={() => testLlmMut.mutate()} disabled={testLlmMut.isPending} className="h-9 px-4 text-muted-foreground hover:text-white font-medium">
                {testLlmMut.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : "Test connection"}
              </Button>
            </div>
          </div>
        </IntegrationCard>
      </div>

      {/* ── ALERTS & NOTIFICATIONS ── */}
      <div className="space-y-3">
        <div className="text-[10px] tracking-widest uppercase font-semibold text-muted-foreground pl-1">Alerts & Notifications</div>
        
        {/* Slack */}
        <IntegrationCard
          name="Slack"
          description="Auto-post structured QA incident reports to your Slack channel when a test fails."
          logo={<SlackLogo />}
          logoBgClass="bg-white"
          isConnected={slackData?.slack_webhook_url_set ?? false}
          statusCaption="Posting to workspace"
          emptyStateText="Not connected yet — add your Slack Incoming Webhook URL to automatically receive rich failure alerts."
          onDisconnect={() => saveSlackMut.mutate()}
        >
          <div className="space-y-6">
            <MaskedCredentialField 
              label="Incoming Webhook URL" 
              placeholder="https://hooks.slack.com/services/T.../B..." 
              value={slackWebhookUrl} 
              onChange={setSlackWebhookUrl} 
              isSet={slackData?.slack_webhook_url_set ?? false} 
              isMaskedFallback="https://hooks.slack.com/services/T0••••/B0••••"
              isSaving={saveSlackMut.isPending}
              onSave={() => saveSlackMut.mutate()} 
            />
            
            <div className="space-y-2 pt-1">
              <Label className="text-[10px] tracking-widest font-semibold uppercase text-muted-foreground">Your Leaka Dashboard URL</Label>
              <Input className="font-mono bg-[#0B0E14] border-transparent h-10 text-sm focus-visible:ring-1 focus-visible:ring-indigo-500/50" placeholder="https://app.leaka.ai" value={slackDashboardUrl} onChange={e => setSlackDashboardUrl(e.target.value)} />
            </div>

            <div className="flex items-center justify-between rounded-lg bg-[#0B0E14] p-4 border border-transparent">
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">Auto-alert on test failure</p>
                <p className="text-xs text-muted-foreground max-w-[85%] leading-relaxed">
                  Automatically send a QA incident report to Slack when a test completes with a failure.
                </p>
              </div>
              <button
                role="switch"
                aria-checked={slackAutoAlert}
                onClick={() => setSlackAutoAlert((v) => !v)}
                className={cn("relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none", slackAutoAlert ? "bg-emerald-500" : "bg-muted-foreground/30")}
              >
                <span className={cn("pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform", slackAutoAlert ? "translate-x-4" : "translate-x-0")} />
              </button>
            </div>

            <details className="group border border-border/30 rounded-lg overflow-hidden bg-[#0B0E14]/50">
              <summary className="flex cursor-pointer items-center justify-between px-4 py-3 text-xs font-medium text-muted-foreground hover:text-white select-none">
                What gets sent →
                <ChevronDown className="w-4 h-4 transition-transform group-open:-rotate-180" />
              </summary>
              <div className="px-4 pb-4 pt-2 text-xs text-muted-foreground/80 space-y-2 border-t border-border/20">
                <ul className="list-disc list-inside space-y-1.5 ml-1">
                  <li>Test name, timestamp, and target environment</li>
                  <li>Expected vs. actual result from the agent execution</li>
                  <li>Failed step number and the action that triggered the failure</li>
                  <li>Reproduction steps derived from the actual execution trace</li>
                </ul>
              </div>
            </details>

            <div className="flex items-center gap-4 pt-4 border-t border-border/20 mt-6">
              <Button onClick={() => saveSlackMut.mutate()} disabled={saveSlackMut.isPending} className="bg-indigo-300 text-indigo-950 hover:bg-indigo-400 font-semibold h-9 px-5">
                {saveSlackMut.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : "Save Slack settings"}
              </Button>
              <Button variant="ghost" onClick={() => testSlackMut.mutate()} disabled={testSlackMut.isPending || !slackData?.slack_webhook_url_set} className="h-9 px-4 text-muted-foreground hover:text-white font-medium">
                {testSlackMut.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : "Send test ping"}
              </Button>
            </div>
          </div>
        </IntegrationCard>

        {/* Resend */}
        <IntegrationCard
          name="Email Alerts (Resend)"
          description="Send failure alerts with screenshot attachments via Resend."
          logo={<ResendLogo />}
          logoBgClass="bg-black border border-white/10"
          isConnected={data?.resend.api_key_set ?? false}
          emptyStateText="Not connected yet — add your Resend API key to start receiving email alerts."
          onDisconnect={() => saveMut.mutate({ resend_api_key: "" })}
        >
          <div className="space-y-6">
            <MaskedCredentialField 
              label="Resend API Key" 
              placeholder="re_..." 
              value={resendKey} 
              onChange={setResendKey} 
              isSet={data?.resend.api_key_set ?? false} 
              isMaskedFallback="re_••••••••••••••••"
              isSaving={saveMut.isPending}
              onSave={() => saveMut.mutate({ resend_api_key: resendKey || undefined })} 
            />
            <div className="space-y-2 pt-1">
              <Label className="text-[10px] tracking-widest font-semibold uppercase text-muted-foreground">From address</Label>
              <Input className="font-mono bg-[#0B0E14] border-transparent h-10 text-sm focus-visible:ring-1 focus-visible:ring-indigo-500/50" placeholder="Leaka AI <qa@yourdomain.com>" value={emailFrom} onChange={e => setEmailFrom(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label className="text-[10px] tracking-widest font-semibold uppercase text-muted-foreground">Alert recipients (comma-separated)</Label>
              <Input className="font-mono bg-[#0B0E14] border-transparent h-10 text-sm focus-visible:ring-1 focus-visible:ring-indigo-500/50" placeholder="eng@company.com, cto@company.com" value={emailTo} onChange={e => setEmailTo(e.target.value)} />
            </div>
            <div className="flex items-center gap-4 pt-4 border-t border-border/20 mt-6">
              <Button onClick={() => saveMut.mutate({ resend_api_key: resendKey || undefined, email_from: emailFrom || undefined, email_alert_to: emailTo || undefined })} disabled={saveMut.isPending} className="bg-indigo-300 text-indigo-950 hover:bg-indigo-400 font-semibold h-9 px-5">
                {saveMut.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : "Save email settings"}
              </Button>
            </div>
          </div>
        </IntegrationCard>
      </div>

      {/* ── ISSUE TRACKING ── */}
      <div className="space-y-3">
        <div className="text-[10px] tracking-widest uppercase font-semibold text-muted-foreground pl-1">Issue Tracking</div>
        <IntegrationCard
          name="Linear"
          description="Auto-create bug tickets in your engineering backlog when a test fails."
          logo={<LinearLogo />}
          logoBgClass="bg-[#5E6AD2]"
          isConnected={data?.linear.api_key_set ?? false}
          emptyStateText="Not connected yet — add your API key to start auto-filing bug tickets."
          onDisconnect={() => saveMut.mutate({ linear_api_key: "" })}
        >
          <div className="space-y-6">
            <MaskedCredentialField 
              label="Linear API Key" 
              placeholder="lin_api_..." 
              value={linearKey} 
              onChange={setLinearKey} 
              isSet={data?.linear.api_key_set ?? false} 
              isMaskedFallback="lin_api_••••••••••••••••"
              isSaving={saveMut.isPending}
              onSave={() => saveMut.mutate({ linear_api_key: linearKey || undefined })} 
            />
            <div className="space-y-2 pt-1">
              <Label className="text-[10px] tracking-widest font-semibold uppercase text-muted-foreground">Team ID</Label>
              <Input className="font-mono bg-[#0B0E14] border-transparent h-10 text-sm focus-visible:ring-1 focus-visible:ring-indigo-500/50" placeholder="e.g. abc123de-..." value={linearTeam} onChange={e => setLinearTeam(e.target.value)} />
            </div>
            <div className="flex items-center gap-4 pt-4 border-t border-border/20 mt-6">
              <Button onClick={() => saveMut.mutate({ linear_api_key: linearKey || undefined, linear_team_id: linearTeam || undefined })} disabled={saveMut.isPending} className="bg-indigo-300 text-indigo-950 hover:bg-indigo-400 font-semibold h-9 px-5">
                {saveMut.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : "Save Linear settings"}
              </Button>
            </div>
          </div>
        </IntegrationCard>
      </div>

      {/* ── CI / CD ── */}
      <div className="space-y-3">
        <div className="text-[10px] tracking-widest uppercase font-semibold text-muted-foreground pl-1">CI / CD</div>
        <Card className="border-0 bg-[#161922] p-6 overflow-hidden relative shadow-sm border-t border-t-muted/10">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-10 h-10 rounded-xl bg-white grid place-items-center shadow-sm shrink-0">
              <Github className="w-5 h-5 text-black" />
            </div>
            <div>
              <h3 className="font-medium text-foreground text-sm">GitHub Actions & Webhooks</h3>
              <p className="text-sm text-muted-foreground mt-0.5 leading-tight">
                Trigger Leaka QA suites automatically from your deployment pipelines.
              </p>
            </div>
          </div>
          
          <div className="space-y-2 pt-2 border-t border-border/20">
            <Label className="text-[10px] tracking-widest font-semibold uppercase text-muted-foreground mt-4 block">CI Webhook Token</Label>
            <div className="flex items-center gap-2">
              <div className="h-10 flex-1 flex items-center px-4 rounded-md bg-[#0B0E14] border border-transparent font-mono text-sm text-muted-foreground/70 truncate">
                {data?.ci.webhook_token ? `revguard-ci-token-${data.ci.webhook_token.slice(0,8)}••••••••` : "Not generated yet"}
              </div>
              <Button size="icon" variant="ghost" className="h-10 w-10 shrink-0 text-muted-foreground hover:text-white bg-[#161922] border-transparent" onClick={() => copyToClip(data?.ci.webhook_token ?? "")} disabled={!data?.ci.webhook_token}>
                <Copy className="w-4 h-4" />
              </Button>
              <Button variant="ghost" className="h-10 text-muted-foreground hover:text-white font-medium bg-[#161922]/50 border-transparent" onClick={() => {
                const newToken = `revguard-ci-token-${Math.random().toString(36).substring(2, 10)}${Math.random().toString(36).substring(2, 10)}`;
                setCiToken(newToken);
                saveMut.mutate({ ci_webhook_token: newToken });
              }} disabled={saveMut.isPending}>
                <RefreshCcw className="w-3.5 h-3.5 mr-2" /> Regenerate
              </Button>
            </div>
          </div>
          
          <div className="mt-6 flex justify-end">
             <Link href="/ci" className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors inline-flex items-center font-medium">
               Full setup guide <span className="ml-1 text-[10px] leading-none mb-[2px]">→</span>
             </Link>
          </div>
        </Card>
      </div>
    </div>
  );
}
