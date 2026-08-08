"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api, BACKEND_URL, type RunStatus as RS } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  AlertTriangle, ArrowLeft, CheckCircle2, CircleDashed, Loader2,
  Mail, Ticket, XCircle, ClipboardCopy, X, CheckCheck, Clock,
  Image as ImageIcon, Bell, MousePointerClick, Navigation, Type,
  Search, ScrollText, ArrowRight, Globe, Zap,
} from "lucide-react";
import { formatDate, formatDuration, truncate } from "@/lib/utils";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "@/components/ui/use-toast";

const TERMINAL: RS[] = ["completed", "failed", "cancelled"];

// Parse steps_log JSON safely
interface StepAction {
  step?: number;
  action?: Record<string, unknown>;
  result?: string | null;
  error?: string | null;
  interacted_element?: unknown;
  url?: string | null;
}

function parseStepsLog(raw: string | null | undefined): StepAction[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

// Map action keys to human-readable labels + icons
function actionMeta(action: Record<string, unknown> | undefined): {
  label: string;
  detail: string;
  icon: React.ReactNode;
} {
  if (!action) return { label: "action", detail: "", icon: <Zap className="w-3 h-3" /> };
  const key = Object.keys(action)[0] || "unknown";
  const val = action[key] as Record<string, unknown> | string | undefined;

  const detail = typeof val === "string" ? val
    : typeof val === "object" && val
      ? (val.url as string) || (val.text as string) || (val.query as string) || JSON.stringify(val).slice(0, 80)
      : "";

  const iconMap: Record<string, React.ReactNode> = {
    navigate: <Navigation className="w-3 h-3" />,
    click: <MousePointerClick className="w-3 h-3" />,
    input: <Type className="w-3 h-3" />,
    search: <Search className="w-3 h-3" />,
    scroll: <ScrollText className="w-3 h-3" />,
    extract: <ArrowRight className="w-3 h-3" />,
    done: <CheckCircle2 className="w-3 h-3" />,
    go_back: <ArrowLeft className="w-3 h-3" />,
  };

  return {
    label: key.replace(/_/g, " "),
    detail: String(detail).slice(0, 120),
    icon: iconMap[key] ?? <Zap className="w-3 h-3" />,
  };
}

// ── Self-healing analysis ─────────────────────────────────────────────────────
// Reads the step list and surfaces evidence of adaptive behaviour —
// things Cypress would have broken on but the agent handled automatically.
interface SelfHealingInsight {
  icon: string;
  text: string;
}

function analyzeSelfHealing(steps: StepAction[], isSuccessful: boolean | null): SelfHealingInsight[] {
  const insights: SelfHealingInsight[] = [];
  if (!steps.length) return insights;

  // Count scroll actions — agent had to explore to find content
  const scrollCount = steps.filter((s) => {
    const key = Object.keys(s.action || {})[0] || "";
    return key === "scroll";
  }).length;
  if (scrollCount > 0) {
    insights.push({
      icon: "↕️",
      text: `Scrolled ${scrollCount} time${scrollCount > 1 ? "s" : ""} to locate content not visible in the initial viewport. Cypress would have thrown "element not found".`,
    });
  }

  // Detected retry/fallback in result text
  const retryStep = steps.find((s) =>
    typeof s.result === "string" &&
    (s.result.toLowerCase().includes("retry") ||
      s.result.toLowerCase().includes("trying") ||
      s.result.toLowerCase().includes("alternative"))
  );
  if (retryStep) {
    insights.push({
      icon: "🔄",
      text: "Agent detected an obstacle and tried an alternative approach automatically.",
    });
  }

  // Multiple URLs visited — agent navigated across pages
  const urls = new Set(steps.map((s) => s.url).filter(Boolean));
  if (urls.size > 1) {
    insights.push({
      icon: "🌐",
      text: `Navigated across ${urls.size} different pages to complete the task — no hard-coded URL paths needed.`,
    });
  }

  // Task completed despite having errors in intermediate steps
  const hasErrors = steps.some((s) => s.error);
  if (hasErrors && isSuccessful) {
    insights.push({
      icon: "♻️",
      text: "Recovered from intermediate errors and still completed the task successfully. Cypress would have stopped at the first failure.",
    });
  }

  return insights;
}

function SelfHealingCard({ steps, isSuccessful }: { steps: StepAction[]; isSuccessful: boolean | null }) {
  const insights = analyzeSelfHealing(steps, isSuccessful);
  if (!insights.length) return null;

  return (
    <Card className="border-emerald-500/30 bg-emerald-500/5">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2 text-emerald-700 dark:text-emerald-400">
          <span>✦</span> Self-healing in action
        </CardTitle>
        <CardDescription>
          Evidence of adaptive behaviour that would have broken a Cypress test.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {insights.map((ins, i) => (
          <div key={i} className="flex items-start gap-3 text-sm">
            <span className="text-base shrink-0 mt-0.5">{ins.icon}</span>
            <p className="text-muted-foreground leading-relaxed">{ins.text}</p>
          </div>
        ))}
        <div className="pt-2 border-t border-emerald-500/20 text-xs text-emerald-700 dark:text-emerald-500">
          Unlike Cypress or Playwright selectors, Leaka AI reasons visually — it adapts to UI changes automatically.
        </div>
      </CardContent>
    </Card>
  );
}

export default function RunDetailPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = params.jobId!;

  const { data, isLoading, isRefetching } = useQuery({
    queryKey: ["run", jobId],
    queryFn: () => api.getRunStatus(jobId),
    refetchInterval: (ctx) => {
      const s = ctx.state.data?.status;
      if (!s || TERMINAL.includes(s)) return false;
      return 3000;
    },
  });

  const linearMut = useMutation({
    mutationFn: () => api.createLinearIssue({ job_id: jobId }),
    onSuccess: (res) => {
      toast({
        title: res.success ? "Linear ticket created" : "Linear ticket failed",
        description: res.success
          ? (res.identifier ? `${res.identifier}: ${res.title}` : "Ticket filed.")
          : "Verify LINEAR_API_KEY and LINEAR_TEAM_ID are set.",
        variant: res.success ? "default" : "destructive",
      });
    },
    onError: (e: Error) => toast({ title: "Linear failed", description: e.message, variant: "destructive" }),
  });

  const emailMut = useMutation({
    mutationFn: () => api.sendFailureEmail(jobId, typeof window !== "undefined" ? `${window.location.origin}/runs` : undefined),
    onSuccess: () => toast({ title: "Failure alert email sent" }),
    onError: (e: Error) => toast({ title: "Email failed", description: e.message, variant: "destructive" }),
  });

  const slackMut = useMutation({
    mutationFn: () => api.sendSlackAlert(jobId, typeof window !== "undefined" ? `${window.location.origin}/runs` : undefined),
    onSuccess: (r) => toast({ title: r.sent ? "Slack alert sent" : "Slack alert failed", variant: r.sent ? "default" : "destructive" }),
    onError: (e: Error) => toast({ title: "Slack failed", description: e.message, variant: "destructive" }),
  });

  const cancelMut = useMutation({
    mutationFn: () => api.cancelRun(jobId),
    onSuccess: () => toast({ title: "Run cancelled" }),
    onError: (e: Error) => toast({ title: "Could not cancel", description: e.message, variant: "destructive" }),
  });

  const status = data?.status;
  const isRunning = status === "running" || status === "pending";

  // Use live_steps while running for real-time updates, steps_log after completion
  const stepsSource = (isRunning && data?.live_steps) ? data.live_steps : data?.steps_log;
  const steps = parseStepsLog(stepsSource);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 flex-wrap">
        <Button asChild variant="outline" size="sm">
          <Link href="/dashboard"><ArrowLeft className="w-4 h-4 mr-2" />Dashboard</Link>
        </Button>
        <h1 className="text-xl md:text-2xl font-semibold tracking-tight flex-1 truncate">
          {isLoading ? <Skeleton className="h-6 w-64 inline-block align-middle" /> : data?.name}
        </h1>
        {data && <StatusBadge status={data.status} />}
        {isRunning && (
          <Button size="sm" variant="destructive" disabled={cancelMut.isPending} onClick={() => cancelMut.mutate()}>
            {cancelMut.isPending ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <X className="w-3 h-3 mr-1" />}
            Cancel
          </Button>
        )}
        {isRefetching && (
          <span className="text-xs text-muted-foreground inline-flex items-center gap-1">
            <Loader2 className="w-3 h-3 animate-spin" /> refreshing
          </span>
        )}
      </div>

      {isLoading && <RunSkeleton />}
      {data && (
        <RunView
          data={data}
          steps={steps}
          onEmail={() => emailMut.mutate()}
          onLinear={() => linearMut.mutate()}
          onSlack={() => slackMut.mutate()}
        />
      )}
    </div>
  );
}

function RunView({
  data, steps, onEmail, onLinear, onSlack,
}: {
  data: Awaited<ReturnType<typeof api.getRunStatus>>;
  steps: StepAction[];
  onEmail: () => void;
  onLinear: () => void;
  onSlack: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const copyClip = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <>
      {/* Status banners */}
      {data.status === "failed" && (
        <Alert variant="destructive">
          <XCircle className="w-4 h-4" />
          <AlertTitle>Test failed</AlertTitle>
          <AlertDescription>
            The browser-use agent could not complete this run. Review the steps timeline and failure screenshot below.
          </AlertDescription>
        </Alert>
      )}
      {data.status === "completed" && (
        <Alert className="bg-emerald-500/10 border-emerald-500/40 text-emerald-700 dark:text-emerald-300">
          <CheckCircle2 className="w-4 h-4" />
          <AlertTitle>Test passed</AlertTitle>
          <AlertDescription>
            Agent completed {data.total_steps ?? "—"} steps in {formatDuration(data.duration_seconds)}.
          </AlertDescription>
        </Alert>
      )}
      {data.status === "pending" && (
        <Alert>
          <CircleDashed className="w-4 h-4" />
          <AlertTitle>Awaiting worker</AlertTitle>
          <AlertDescription>Job enqueued — worker will pick it up shortly.</AlertDescription>
        </Alert>
      )}
      {data.status === "running" && (
        <Alert className="bg-blue-500/10 border-blue-500/30 text-blue-700 dark:text-blue-300">
          <Loader2 className="w-4 h-4 animate-spin" />
          <AlertTitle>Running · {data.progress?.stage || "executing steps"}</AlertTitle>
          <AlertDescription>UI refreshes every 3 seconds automatically.</AlertDescription>
        </Alert>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <SummaryCard icon={<Clock className="w-4 h-4" />} label="Duration">
          {formatDuration(data.duration_seconds)}
        </SummaryCard>
        <SummaryCard icon={<ScrollText className="w-4 h-4" />} label="Steps">
          {data.total_steps ?? 0}
        </SummaryCard>
        <SummaryCard icon={<Globe className="w-4 h-4" />} label="URLs visited">
          {(() => {
            try { return data.visited_urls ? JSON.parse(data.visited_urls).length : 0; } catch { return 0; }
          })()}
        </SummaryCard>
        <SummaryCard icon={<AlertTriangle className="w-4 h-4" />} label="Visual proof">
          {data.screenshots.length > 0
            ? <span className="text-emerald-600 dark:text-emerald-400">{data.screenshots.length} screenshots</span>
            : <span className="text-muted-foreground">none</span>
          }
        </SummaryCard>
      </div>

      <Tabs defaultValue="steps" className="space-y-4">
        <TabsList>
          <TabsTrigger value="steps">
            Steps
            {steps.length > 0 && <span className="ml-1.5 text-xs text-muted-foreground">({steps.length})</span>}
          </TabsTrigger>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="screenshots">
            Screenshots
            {data.screenshots.length > 0 && <span className="ml-1.5 text-xs text-muted-foreground">({data.screenshots.length})</span>}
          </TabsTrigger>
          <TabsTrigger value="integrations">Integrations</TabsTrigger>
        </TabsList>

        {/* ── STEPS TIMELINE ── */}
        <TabsContent value="steps" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <ScrollText className="w-4 h-4" />
                Agent steps timeline
              </CardTitle>
              <CardDescription>
                Every action the browser-use agent took, in order. Failure points are highlighted.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {steps.length === 0 ? (
                <div className="text-sm text-muted-foreground py-8 text-center">
                  {data.status === "pending" || data.status === "running"
                    ? "Steps will appear here as the agent runs…"
                    : "No steps recorded for this run."}
                </div>
              ) : (
                <div className="relative">
                  {/* Vertical line */}
                  <div className="absolute left-[18px] top-0 bottom-0 w-px bg-border" />
                  <ol className="space-y-1 pl-10">
                    {steps.map((step, i) => {
                      const meta = actionMeta(step.action);
                      const hasError = Boolean(step.error);
                      const isDone = meta.label === "done";
                      return (
                        <li key={i} className="relative">
                          {/* Dot */}
                          <span className={[
                            "absolute -left-[26px] top-2 w-5 h-5 rounded-full border-2 flex items-center justify-center text-[10px] shrink-0",
                            hasError
                              ? "bg-destructive/10 border-destructive text-destructive"
                              : isDone
                                ? "bg-emerald-500/10 border-emerald-500 text-emerald-600"
                                : "bg-background border-border text-muted-foreground",
                          ].join(" ")}>
                            {hasError ? <X className="w-2.5 h-2.5" /> : isDone ? <CheckCircle2 className="w-2.5 h-2.5" /> : meta.icon}
                          </span>
                          <div className={[
                            "rounded-md border px-3 py-2 text-sm",
                            hasError ? "border-destructive/40 bg-destructive/5" : "bg-muted/30",
                          ].join(" ")}>
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-xs font-mono text-muted-foreground w-10 shrink-0">
                                #{(step.step ?? i) + 1}
                              </span>
                              <Badge variant={hasError ? "destructive" : "secondary"} className="text-xs capitalize">
                                {meta.label}
                              </Badge>
                              {meta.detail && (
                                <span className="text-xs text-muted-foreground truncate max-w-sm">
                                  {meta.detail}
                                </span>
                              )}
                            </div>
                            {step.result && (
                              <p className="text-xs text-muted-foreground mt-1 pl-12 truncate">
                                → {String(step.result).slice(0, 160)}
                              </p>
                            )}
                            {step.error && (
                              <p className="text-xs text-destructive mt-1 pl-12">
                                ✗ {String(step.error).slice(0, 200)}
                              </p>
                            )}
                          </div>
                        </li>
                      );
                    })}
                    {/* Live pulse — show when agent is still running */}
                    {(data.status === "running") && (
                      <li className="relative">
                        <span className="absolute -left-[26px] top-2 w-5 h-5 rounded-full border-2 border-blue-400 bg-blue-400/10 flex items-center justify-center">
                          <Loader2 className="w-2.5 h-2.5 text-blue-500 animate-spin" />
                        </span>
                        <div className="rounded-md border border-blue-400/30 bg-blue-400/5 px-3 py-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-mono text-muted-foreground w-10 shrink-0">…</span>
                            <span className="text-xs text-blue-600 dark:text-blue-400 animate-pulse">
                              Agent is working…
                            </span>
                          </div>
                        </div>
                      </li>
                    )}
                  </ol>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Self-healing insights — shown when run is complete */}
          {data.status !== "running" && data.status !== "pending" && steps.length > 0 && (
            <SelfHealingCard steps={steps} isSuccessful={data.is_successful ?? null} />
          )}

          {/* Final result inline in steps tab */}
          {data.final_result && (            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  Final result
                </CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="whitespace-pre-wrap text-sm bg-muted/50 p-4 rounded-md border font-mono">
                  {data.final_result}
                </pre>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ── OVERVIEW ── */}
        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <ClipboardCopy className="w-4 h-4" />Prompt
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="relative">
                <pre className="whitespace-pre-wrap text-sm bg-muted/50 p-4 rounded-md border font-mono pr-20">
                  {data.prompt}
                </pre>
                <Button variant="outline" size="sm" className="absolute top-2 right-2"
                  onClick={() => copyClip(data.prompt)}>
                  {copied ? <><CheckCheck className="w-3 h-3 mr-1" />Copied</> : <><ClipboardCopy className="w-3 h-3 mr-1" />Copy</>}
                </Button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 text-sm gap-3">
                <Field label="Job ID" value={<code className="text-xs break-all">{data.job_id}</code>} />
                <Field label="Started" value={formatDate(data.started_at ?? data.created_at)} />
                <Field label="Completed" value={formatDate(data.completed_at)} />
                <Field label="Target URL" override={data.target_url
                  ? <a className="underline truncate block" target="_blank" rel="noreferrer" href={data.target_url}>{truncate(data.target_url, 60)}</a>
                  : undefined} value="N/A" />
                {data.result_summary && (
                  <Field label="Summary" value={data.result_summary} />
                )}
              </div>
            </CardContent>
          </Card>

          {data.error_message && (
            <Card className="border-destructive/40">
              <CardHeader>
                <CardTitle className="text-base text-destructive flex items-center gap-2">
                  <XCircle className="w-4 h-4" />Error
                </CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="whitespace-pre-wrap text-sm bg-destructive/5 text-destructive/90 p-4 rounded-md border border-destructive/30 font-mono max-h-80 overflow-auto">
                  {data.error_message}
                </pre>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ── SCREENSHOTS ── */}
        <TabsContent value="screenshots">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Screenshots</CardTitle>
              <CardDescription>
                Captured at each step. The failure point is highlighted in red.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!data.screenshots.length ? (
                <div className="text-sm text-muted-foreground py-10 text-center">No screenshots captured.</div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {data.screenshots.map((s) => (
                    <div key={s.id} className={"rounded-md border overflow-hidden " + (s.is_failure_point ? "ring-2 ring-destructive/60" : "")}>
                      <div className="flex items-center justify-between px-3 py-2 bg-muted/50 border-b text-xs">
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <ImageIcon className="w-3 h-3" />
                          Step {s.step_index ?? "—"}
                          {s.is_failure_point && (
                            <span className="ml-1 inline-flex items-center gap-1 text-destructive font-medium">
                              <X className="w-3 h-3" /> failure point
                            </span>
                          )}
                        </div>
                        {s.caption && <span className="truncate max-w-[280px]">{truncate(s.caption, 50)}</span>}
                      </div>
                      <a href={`${BACKEND_URL}/api/screenshots/${s.id}`} target="_blank" rel="noreferrer" className="block bg-black/5">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={`${BACKEND_URL}/api/screenshots/${s.id}`}
                          alt={`step ${s.step_index ?? ""}`}
                          className="w-full h-auto max-h-[480px] object-contain bg-muted cursor-zoom-in"
                        />
                      </a>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── INTEGRATIONS ── */}
        <TabsContent value="integrations">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2"><Ticket className="w-4 h-4" />Linear ticket</CardTitle>
                <CardDescription>File a bug report with reproduction steps to your engineering backlog.</CardDescription>
              </CardHeader>
              <CardContent>
                <Button variant="outline" onClick={onLinear}>
                  <Ticket className="w-4 h-4 mr-2" />Create Linear ticket
                </Button>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2"><Mail className="w-4 h-4" />Email alert</CardTitle>
                <CardDescription>Send failure alert with screenshot attachment via Resend.</CardDescription>
              </CardHeader>
              <CardContent>
                <Button variant="outline" onClick={onEmail}>
                  <Mail className="w-4 h-4 mr-2" />Send failure alert
                </Button>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2"><Bell className="w-4 h-4" />Slack alert</CardTitle>
                <CardDescription>Post a rich failure block to your configured Slack channel.</CardDescription>
              </CardHeader>
              <CardContent>
                <Button variant="outline" onClick={onSlack}>
                  <Bell className="w-4 h-4 mr-2" />Send Slack alert
                </Button>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </>
  );
}

function SummaryCard({ icon, label, children }: { icon: React.ReactNode; label: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center gap-2 text-xs text-muted-foreground uppercase tracking-wide">
          <span className="text-primary">{icon}</span>{label}
        </div>
        <div className="mt-1 text-2xl font-semibold">{children}</div>
      </CardContent>
    </Card>
  );
}

function Field({ label, value, override }: { label: string; value?: React.ReactNode; override?: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground uppercase tracking-wide mb-1">{label}</div>
      <div>{override ?? value}</div>
    </div>
  );
}

function RunSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-12 w-full" />
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-20" />)}
      </div>
      <Skeleton className="h-96 w-full" />
    </div>
  );
}
