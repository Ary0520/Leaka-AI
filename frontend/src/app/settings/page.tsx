"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Loader2, Save, CheckCircle2, Ticket, Mail, Bell, Zap, Webhook, Settings2 } from "lucide-react";
import { toast } from "@/components/ui/use-toast";

type IntegrationSettings = Awaited<ReturnType<typeof api.getIntegrationSettings>>;

const LLM_PROVIDERS = ["openrouter", "openai", "anthropic", "ollama"] as const;

function StatusDot({ set }: { set: boolean }) {
  return (
    <span className={`inline-block w-2 h-2 rounded-full ${set ? "bg-emerald-500" : "bg-muted-foreground/30"}`} />
  );
}

function SectionHeader({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <CardHeader>
      <CardTitle className="text-base flex items-center gap-2">{icon}{title}</CardTitle>
      <CardDescription>{description}</CardDescription>
    </CardHeader>
  );
}

export default function SettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["integration-settings"],
    queryFn: () => api.getIntegrationSettings(),
  });

  // Local form state
  const [linearKey, setLinearKey] = useState("");
  const [linearTeam, setLinearTeam] = useState("");
  const [resendKey, setResendKey] = useState("");
  const [emailFrom, setEmailFrom] = useState("");
  const [emailTo, setEmailTo] = useState("");
  const [slackUrl, setSlackUrl] = useState("");
  const [llmProvider, setLlmProvider] = useState("");
  const [openrouterKey, setOpenrouterKey] = useState("");
  const [openrouterModel, setOpenrouterModel] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [anthropicKey, setAnthropicKey] = useState("");
  const [ciToken, setCiToken] = useState("");

  // Populate non-secret fields from server
  useEffect(() => {
    if (!data) return;
    setLinearTeam(data.linear.team_id ?? "");
    setEmailFrom(data.resend.email_from ?? "");
    setEmailTo(data.resend.email_alert_to ?? "");
    setLlmProvider(data.llm.provider ?? "");
    setOpenrouterModel(data.llm.openrouter_model ?? "");
    setCiToken(data.ci.webhook_token ?? "");
  }, [data]);

  const saveMut = useMutation({
    mutationFn: (payload: Parameters<typeof api.updateIntegrationSettings>[0]) =>
      api.updateIntegrationSettings(payload),
    onSuccess: (r) => {
      toast({ title: "Settings saved", description: r.message });
      qc.invalidateQueries({ queryKey: ["integration-settings"] });
    },
    onError: (e: Error) => toast({ title: "Save failed", description: e.message, variant: "destructive" }),
  });

  const saveSection = (payload: Parameters<typeof api.updateIntegrationSettings>[0]) => {
    saveMut.mutate(payload);
  };

  if (isLoading) return (
    <div className="space-y-4 max-w-2xl">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="h-40 rounded-lg bg-muted animate-pulse" />
      ))}
    </div>
  );

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Settings2 className="w-6 h-6" /> Integration Settings
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Configure your integrations. Secrets are stored in the backend <code>.env</code> file.
          A backend restart is required for LLM changes to take effect.
        </p>
      </div>

      {/* ── LLM ── */}
      <Card>
        <SectionHeader icon={<Zap className="w-4 h-4 text-primary" />} title="LLM Provider"
          description="The AI model that drives the browser-use agent. Restart backend after changing." />
        <CardContent className="space-y-4">
          <div>
            <Label>Provider</Label>
            <Select value={llmProvider} onValueChange={setLlmProvider}>
              <SelectTrigger className="mt-1"><SelectValue placeholder="Select provider" /></SelectTrigger>
              <SelectContent>
                {LLM_PROVIDERS.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          {llmProvider === "openrouter" && (
            <>
              <div>
                <Label>OpenRouter API key <StatusDot set={data?.llm.openrouter_key_set ?? false} /></Label>
                <Input className="mt-1 font-mono" type="password" placeholder={data?.llm.openrouter_key_set ? "sk-or-v1-●●●●●●●●..." : "sk-or-v1-..."} value={openrouterKey} onChange={e => setOpenrouterKey(e.target.value)} />
              </div>
              <div>
                <Label>Model</Label>
                <Input className="mt-1 font-mono" placeholder="openai/gpt-4o-mini" value={openrouterModel} onChange={e => setOpenrouterModel(e.target.value)} />
                <p className="text-xs text-muted-foreground mt-1">e.g. openai/gpt-4o-mini · anthropic/claude-sonnet-4 · google/gemma-4-31b-it:free</p>
              </div>
            </>
          )}
          {llmProvider === "openai" && (
            <div>
              <Label>OpenAI API key <StatusDot set={data?.llm.openai_key_set ?? false} /></Label>
              <Input className="mt-1 font-mono" type="password" placeholder={data?.llm.openai_key_set ? "sk-●●●●..." : "sk-..."} value={openaiKey} onChange={e => setOpenaiKey(e.target.value)} />
            </div>
          )}
          {llmProvider === "anthropic" && (
            <div>
              <Label>Anthropic API key <StatusDot set={data?.llm.anthropic_key_set ?? false} /></Label>
              <Input className="mt-1 font-mono" type="password" placeholder={data?.llm.anthropic_key_set ? "sk-ant-●●●●..." : "sk-ant-..."} value={anthropicKey} onChange={e => setAnthropicKey(e.target.value)} />
            </div>
          )}
          {llmProvider === "ollama" && (
            <p className="text-sm text-muted-foreground">Ollama runs locally — no API key needed. Make sure Ollama is running on port 11434.</p>
          )}
          <Button size="sm" disabled={saveMut.isPending} onClick={() => saveSection({
            llm_provider: llmProvider || undefined,
            llm_model_openrouter: openrouterModel || undefined,
            openrouter_api_key: openrouterKey || undefined,
            openai_api_key: openaiKey || undefined,
            anthropic_api_key: anthropicKey || undefined,
          })}>
            {saveMut.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
            Save LLM settings
          </Button>
        </CardContent>
      </Card>

      {/* ── LINEAR ── */}
      <Card>
        <SectionHeader icon={<Ticket className="w-4 h-4 text-primary" />} title="Linear"
          description="Auto-create bug tickets in your engineering backlog when a test fails." />
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2">
            <StatusDot set={data?.linear.api_key_set ?? false} />
            <span className="text-sm text-muted-foreground">
              {data?.linear.api_key_set ? `Connected (${data.linear.api_key})` : "Not configured"}
            </span>
          </div>
          <div>
            <Label>API key</Label>
            <Input className="mt-1 font-mono" type="password" placeholder="lin_api_..." value={linearKey} onChange={e => setLinearKey(e.target.value)} />
            <p className="text-xs text-muted-foreground mt-1">Get from Linear → Settings → API → Personal API keys</p>
          </div>
          <div>
            <Label>Team ID</Label>
            <Input className="mt-1 font-mono" placeholder="e.g. abc123de-..." value={linearTeam} onChange={e => setLinearTeam(e.target.value)} />
            <p className="text-xs text-muted-foreground mt-1">Found in Linear → Settings → General → Team ID</p>
          </div>
          <Button size="sm" disabled={saveMut.isPending} onClick={() => saveSection({
            linear_api_key: linearKey || undefined,
            linear_team_id: linearTeam || undefined,
          })}>
            {saveMut.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
            Save Linear settings
          </Button>
        </CardContent>
      </Card>

      {/* ── RESEND ── */}
      <Card>
        <SectionHeader icon={<Mail className="w-4 h-4 text-primary" />} title="Email alerts (Resend)"
          description="Send failure alerts with screenshot attachments via Resend." />
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2">
            <StatusDot set={data?.resend.api_key_set ?? false} />
            <span className="text-sm text-muted-foreground">
              {data?.resend.api_key_set ? `Connected (${data.resend.api_key})` : "Not configured"}
            </span>
          </div>
          <div>
            <Label>Resend API key</Label>
            <Input className="mt-1 font-mono" type="password" placeholder="re_..." value={resendKey} onChange={e => setResendKey(e.target.value)} />
            <p className="text-xs text-muted-foreground mt-1">Get from resend.com → API Keys</p>
          </div>
          <div>
            <Label>From address</Label>
            <Input className="mt-1" placeholder="Leaka AI <qa@yourdomain.com>" value={emailFrom} onChange={e => setEmailFrom(e.target.value)} />
          </div>
          <div>
            <Label>Alert recipients (comma-separated)</Label>
            <Input className="mt-1" placeholder="eng@company.com, cto@company.com" value={emailTo} onChange={e => setEmailTo(e.target.value)} />
          </div>
          <Button size="sm" disabled={saveMut.isPending} onClick={() => saveSection({
            resend_api_key: resendKey || undefined,
            email_from: emailFrom || undefined,
            email_alert_to: emailTo || undefined,
          })}>
            {saveMut.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
            Save email settings
          </Button>
        </CardContent>
      </Card>

      {/* ── SLACK ── */}
      <Card>
        <SectionHeader icon={<Bell className="w-4 h-4 text-primary" />} title="Slack"
          description="Post rich failure alerts to a Slack channel via Incoming Webhooks." />
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2">
            <StatusDot set={data?.slack.webhook_url_set ?? false} />
            <span className="text-sm text-muted-foreground">
              {data?.slack.webhook_url_set ? `Connected (${data.slack.webhook_url})` : "Not configured"}
            </span>
          </div>
          <div>
            <Label>Incoming webhook URL</Label>
            <Input className="mt-1 font-mono" type="password" placeholder="https://hooks.slack.com/services/..." value={slackUrl} onChange={e => setSlackUrl(e.target.value)} />
            <p className="text-xs text-muted-foreground mt-1">Create at api.slack.com → Your Apps → Incoming Webhooks</p>
          </div>
          <Button size="sm" disabled={saveMut.isPending} onClick={() => saveSection({ slack_webhook_url: slackUrl || undefined })}>
            {saveMut.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
            Save Slack settings
          </Button>
        </CardContent>
      </Card>

      {/* ── CI TOKEN ── */}
      <Card>
        <SectionHeader icon={<Webhook className="w-4 h-4 text-primary" />} title="CI / CD webhook token"
          description="The secret token used to authenticate GitHub Actions and other CI triggers." />
        <CardContent className="space-y-4">
          <div>
            <Label>Webhook token</Label>
            <Input className="mt-1 font-mono" value={ciToken} onChange={e => setCiToken(e.target.value)} placeholder="revguard-ci-token-..." />
            <p className="text-xs text-muted-foreground mt-1">Add as <code>LEAKA_CI_TOKEN</code> secret in GitHub Actions.</p>
          </div>
          <Button size="sm" disabled={saveMut.isPending} onClick={() => saveSection({ ci_webhook_token: ciToken || undefined })}>
            {saveMut.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
            Save CI token
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
