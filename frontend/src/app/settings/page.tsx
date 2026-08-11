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
import { Loader2, Save, CheckCircle2, Ticket, Mail, Bell, Zap, Webhook, Settings2, Send, FlaskConical } from "lucide-react";
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

// ── Slack settings card (per-user, stored in DB) ─────────────────────────────
function SlackSettingsCard() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["user-slack-settings"],
    queryFn: () => api.getUserSlackSettings(),
  });

  const [webhookUrl, setWebhookUrl] = useState("");
  const [autoAlert, setAutoAlert] = useState(true);
  const [dashboardUrl, setDashboardUrl] = useState("");
  const [pingResult, setPingResult] = useState<{ ok: boolean; message: string } | null>(null);

  useEffect(() => {
    if (!data) return;
    setAutoAlert(data.slack_auto_alert_on_failure);
    setDashboardUrl(data.dashboard_base_url ?? "");
  }, [data]);

  const saveMut = useMutation({
    mutationFn: () =>
      api.updateUserSlackSettings({
        slack_webhook_url: webhookUrl || undefined,
        slack_auto_alert_on_failure: autoAlert,
        dashboard_base_url: dashboardUrl || undefined,
      }),
    onSuccess: (r) => {
      toast({ title: "Slack settings saved", description: r.message });
      setWebhookUrl("");
      qc.invalidateQueries({ queryKey: ["user-slack-settings"] });
    },
    onError: (e: Error) =>
      toast({ title: "Save failed", description: e.message, variant: "destructive" }),
  });

  const pingMut = useMutation({
    mutationFn: () => api.testSlackPing(),
    onSuccess: (r) => {
      setPingResult(r);
      toast({
        title: r.ok ? "Ping sent ✓" : "Ping failed",
        description: r.message,
        variant: r.ok ? "default" : "destructive",
      });
    },
    onError: (e: Error) =>
      toast({ title: "Ping failed", description: e.message, variant: "destructive" }),
  });

  if (isLoading) return <div className="h-48 rounded-lg bg-muted animate-pulse" />;

  return (
    <Card>
      <SectionHeader
        icon={<Bell className="w-4 h-4 text-primary" />}
        title="Slack — QA Incident Alerts"
        description="Auto-post structured QA incident reports to your Slack channel when a test fails. Each alert includes the failure summary, reproduction steps, evidence links, an automated assessment of the likely failure category, and suggested severity. No cost — uses Slack Incoming Webhooks."
      />
      <CardContent className="space-y-5">

        {/* Connection status */}
        <div className="flex items-center gap-2">
          <StatusDot set={data?.slack_webhook_url_set ?? false} />
          <span className="text-sm text-muted-foreground">
            {data?.slack_webhook_url_set
              ? `Webhook connected (${data.slack_webhook_url_masked})`
              : "Not connected"}
          </span>
        </div>

        {/* Webhook URL */}
        <div>
          <Label>Incoming webhook URL</Label>
          <Input
            className="mt-1 font-mono"
            type="password"
            placeholder={
              data?.slack_webhook_url_set
                ? "Enter new URL to replace current webhook"
                : "https://hooks.slack.com/services/T…/B…/…"
            }
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
          />
          <p className="text-xs text-muted-foreground mt-1">
            Create a free Slack app at{" "}
            <a
              href="https://api.slack.com/apps"
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
            >
              api.slack.com/apps
            </a>{" "}
            → Features → Incoming Webhooks → Activate → Add to workspace.
          </p>
        </div>

        {/* Dashboard base URL */}
        <div>
          <Label>Your Leaka dashboard URL</Label>
          <Input
            className="mt-1 font-mono"
            placeholder="https://app.leaka.ai  or  http://localhost:3000"
            value={dashboardUrl}
            onChange={(e) => setDashboardUrl(e.target.value)}
          />
          <p className="text-xs text-muted-foreground mt-1">
            Used to generate deep links in the Slack message pointing directly to the failed run.
          </p>
        </div>

        {/* Auto-alert toggle */}
        <div className="flex items-center justify-between rounded-lg border p-4">
          <div className="space-y-0.5">
            <p className="text-sm font-medium">Auto-alert on test failure</p>
            <p className="text-xs text-muted-foreground">
              When enabled, Leaka automatically sends a QA incident report to Slack
              every time a test run completes with a failure. No manual action required.
            </p>
          </div>
          <button
            role="switch"
            aria-checked={autoAlert}
            onClick={() => setAutoAlert((v) => !v)}
            className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
              autoAlert ? "bg-primary" : "bg-input"
            }`}
          >
            <span
              className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform ${
                autoAlert ? "translate-x-5" : "translate-x-0"
              }`}
            />
          </button>
        </div>

        {/* Alert scope note */}
        <div className="rounded-md bg-muted/50 border p-3 text-xs text-muted-foreground space-y-1">
          <p className="font-medium text-foreground">What the Slack alert contains:</p>
          <ul className="list-disc list-inside space-y-0.5 ml-1">
            <li>Test name, timestamp, and target environment</li>
            <li>Expected vs. actual result from the agent execution</li>
            <li>Failed step number and the action that triggered the failure</li>
            <li>Reproduction steps derived from the actual execution trace</li>
            <li>Automated failure category assessment <em>(not a confirmed root cause)</em></li>
            <li>Suggested severity — labelled as a suggestion, not a QA decision</li>
            <li>Action buttons: View Run, View Screenshot, Technical Evidence, Create Linear Issue</li>
          </ul>
          <p className="mt-2 italic">
            Alerts fire on failure only. Success notifications are not sent.
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <Button
            size="sm"
            disabled={saveMut.isPending}
            onClick={() => saveMut.mutate()}
          >
            {saveMut.isPending ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            Save Slack settings
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={pingMut.isPending || !data?.slack_webhook_url_set}
            onClick={() => pingMut.mutate()}
            title={!data?.slack_webhook_url_set ? "Save a webhook URL first" : ""}
          >
            {pingMut.isPending ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Send className="w-4 h-4 mr-2" />
            )}
            Send test ping
          </Button>
        </div>

        {pingResult && (
          <div
            className={`rounded-md border p-3 text-sm ${
              pingResult.ok
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-300"
                : "bg-destructive/10 border-destructive/30 text-destructive"
            }`}
          >
            {pingResult.ok ? "✅ " : "❌ "}
            {pingResult.message}
          </div>
        )}
      </CardContent>
    </Card>
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
  const [llmTestResult, setLlmTestResult] = useState<{ ok: boolean; provider: string; model: string; detail: string } | null>(null);

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

  const llmTestMut = useMutation({
    mutationFn: () => api.testLlmConnection(),
    onSuccess: (r) => {
      setLlmTestResult(r);
      toast({
        title: r.ok ? "LLM connection verified ✓" : "LLM connection failed",
        description: r.detail,
        variant: r.ok ? "default" : "destructive",
      });
    },
    onError: (e: Error) =>
      toast({ title: "Connection test failed", description: e.message, variant: "destructive" }),
  });

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
          All changes take effect immediately — no restart needed.
        </p>
      </div>

      {/* ── LLM ── */}
      <Card>
        <SectionHeader icon={<Zap className="w-4 h-4 text-primary" />} title="LLM Provider"
          description="The AI model that drives the browser-use agent. Changes apply immediately to the next test run." />
        <CardContent className="space-y-4">
          <div>
            <Label>Provider</Label>
            <Select value={llmProvider} onValueChange={(v) => { setLlmProvider(v); setLlmTestResult(null); }}>
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
          <div className="flex items-center gap-3 flex-wrap">
            <Button size="sm" disabled={saveMut.isPending} onClick={() => {
              setLlmTestResult(null);
              saveSection({
                llm_provider: llmProvider || undefined,
                llm_model_openrouter: openrouterModel || undefined,
                openrouter_api_key: openrouterKey || undefined,
                openai_api_key: openaiKey || undefined,
                anthropic_api_key: anthropicKey || undefined,
              });
            }}>
              {saveMut.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
              Save LLM settings
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={llmTestMut.isPending}
              onClick={() => llmTestMut.mutate()}
            >
              {llmTestMut.isPending
                ? <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                : <FlaskConical className="w-4 h-4 mr-2" />}
              Test connection
            </Button>
          </div>

          {/* Live test result banner */}
          {llmTestResult && (
            <div className={`rounded-md border p-3 text-sm ${
              llmTestResult.ok
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-300"
                : "bg-destructive/10 border-destructive/30 text-destructive"
            }`}>
              <p className="font-medium">
                {llmTestResult.ok ? "✅ Connected" : "❌ Connection failed"}
                <span className="font-normal text-xs ml-2 opacity-70">
                  {llmTestResult.provider} · {llmTestResult.model}
                </span>
              </p>
              <p className="mt-0.5">{llmTestResult.detail}</p>
            </div>
          )}
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
      <SlackSettingsCard />

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
