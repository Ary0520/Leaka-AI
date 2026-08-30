"use client";

/**
 * PRIntelligenceTab — "which tests to run for this change, and what has no
 * safety net" (Layer 4, R6/R7). Built for an engineering lead's workflow:
 * connect a repo once, then for every PR see the affected flows ranked by
 * business risk, the explainable chain (changed file → flow → covering test),
 * a loud warning on any risky change with no coverage, and a one-click
 * "run the exact recommended tests" action into the existing run path.
 *
 * Master–detail layout (institutional pattern): a left rail of ingested PRs +
 * a right impact-analysis pane. Wired to the real endpoints:
 *   GET/POST/DELETE /repo · GET /diffs · GET /diffs/{id}/recommendation ·
 *   POST /diffs/{id}/run
 *
 * Secrets are write-only (token/webhook secret never returned or shown).
 */

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  type CodeDiffOut,
  type FlowMappingOut,
} from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/use-toast";
import { riskClasses, coverageMeta } from "@/lib/intelligence";
import { cn } from "@/lib/utils";
import {
  GitPullRequest, GitBranch, Lock, ShieldAlert, ShieldCheck, Sparkles,
  Play, Plug, FileCode2, ArrowRight, CircleDashed, XCircle, Loader2,
  Unplug, GitCommitHorizontal, ChevronRight,
} from "lucide-react";

export function PRIntelligenceTab({ appId }: { appId: number }) {
  const { data: repo, isLoading } = useQuery({
    queryKey: ["app-repo", appId],
    queryFn: () => api.getRepo(appId),
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-14 w-full rounded-lg" />
        <Skeleton className="h-[520px] w-full rounded-lg" />
      </div>
    );
  }

  if (!repo) return <ConnectRepo appId={appId} />;
  return <ConnectedView appId={appId} repo={repo} />;
}

// ===========================================================================
// STATE 1 — Not connected: focused, reassuring setup.
// ===========================================================================
function ConnectRepo({ appId }: { appId: number }) {
  const qc = useQueryClient();
  const [repoFullName, setRepoFullName] = useState("");
  const [token, setToken] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");

  const connectMut = useMutation({
    mutationFn: () =>
      api.connectRepo(appId, {
        provider: "github",
        repo_full_name: repoFullName.trim(),
        token: token.trim(),
        webhook_secret: webhookSecret.trim() || null,
      }),
    onSuccess: (res) => {
      if (res.status === "connected") {
        toast({ title: "Repository connected", description: `${res.repo_full_name} is now linked.` });
      } else {
        toast({
          title: "Connection failed",
          description: res.last_error || "Could not verify the repository.",
          variant: "destructive",
        });
      }
      qc.invalidateQueries({ queryKey: ["app-repo", appId] });
    },
    onError: (e: Error) =>
      toast({ title: "Could not connect", description: e.message, variant: "destructive" }),
  });

  const canSubmit = repoFullName.includes("/") && token.length > 0 && !connectMut.isPending;

  return (
    <div className="mx-auto max-w-xl">
      <Card>
        <CardContent className="pt-8 pb-7">
          <div className="flex flex-col items-center text-center">
            <div className="w-12 h-12 rounded-xl bg-primary/10 grid place-items-center">
              <GitPullRequest className="w-6 h-6 text-primary" />
            </div>
            <h2 className="mt-3 text-lg font-semibold tracking-tight">Connect your repository</h2>
            <p className="mt-1.5 text-sm text-muted-foreground max-w-md">
              Link a GitHub repo so Leaka maps every pull request to the exact flows it affects —
              and tells you which tests to run before you merge.
            </p>
          </div>

          <div className="mt-7 space-y-5">
            <Field label="Repository">
              <Input
                value={repoFullName}
                onChange={(e) => setRepoFullName(e.target.value)}
                placeholder="owner/repo"
                className="font-mono bg-[#0B0E14] border-transparent h-10 text-sm focus-visible:ring-1 focus-visible:ring-primary/50"
              />
            </Field>

            <Field label="Access token" hint="Encrypted at rest — never shown again.">
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                <Input
                  type="password"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="ghp_••••••••••••••••"
                  className="font-mono bg-[#0B0E14] border-transparent h-10 text-sm pl-9 focus-visible:ring-1 focus-visible:ring-primary/50"
                />
              </div>
            </Field>

            <Field label="Webhook secret" optional hint="For verified push/PR webhook delivery.">
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                <Input
                  type="password"
                  value={webhookSecret}
                  onChange={(e) => setWebhookSecret(e.target.value)}
                  placeholder="optional"
                  className="font-mono bg-[#0B0E14] border-transparent h-10 text-sm pl-9 focus-visible:ring-1 focus-visible:ring-primary/50"
                />
              </div>
            </Field>

            <Button className="w-full" disabled={!canSubmit} onClick={() => connectMut.mutate()}>
              {connectMut.isPending ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Verifying…</>
              ) : (
                <><Plug className="w-4 h-4 mr-2" />Connect GitHub</>
              )}
            </Button>
            <p className="flex items-center justify-center gap-1.5 text-[11px] text-muted-foreground">
              <Lock className="w-3 h-3" /> Your token is stored encrypted and is never returned to the browser.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Field({
  label, children, optional, hint,
}: { label: string; children: React.ReactNode; optional?: boolean; hint?: string }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label className="text-[10px] tracking-widest font-semibold uppercase text-muted-foreground">{label}</Label>
        {optional && <span className="text-[10px] text-muted-foreground/60 uppercase tracking-wide">Optional</span>}
      </div>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground/70">{hint}</p>}
    </div>
  );
}

// ===========================================================================
// STATE 2 — Connected: status bar + master (PR list) / detail (impact).
// ===========================================================================
function ConnectedView({
  appId,
  repo,
}: {
  appId: number;
  repo: NonNullable<Awaited<ReturnType<typeof api.getRepo>>>;
}) {
  const qc = useQueryClient();
  const [selectedDiff, setSelectedDiff] = useState<number | null>(null);

  const { data: diffs, isLoading } = useQuery({
    queryKey: ["app-diffs", appId],
    queryFn: () => api.listDiffs(appId, { limit: 50 }),
  });

  // Auto-select the newest diff once loaded.
  useEffect(() => {
    if (selectedDiff == null && diffs?.diffs?.length) {
      setSelectedDiff(diffs.diffs[0].id);
    }
  }, [diffs, selectedDiff]);

  const disconnectMut = useMutation({
    mutationFn: () => api.disconnectRepo(appId),
    onSuccess: () => {
      toast({ title: "Repository disconnected" });
      qc.invalidateQueries({ queryKey: ["app-repo", appId] });
      qc.invalidateQueries({ queryKey: ["app-diffs", appId] });
    },
  });

  const connected = repo.status === "connected";

  return (
    <div className="space-y-4">
      {/* Status bar */}
      <div className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-2.5">
        <span className={cn("grid place-items-center w-7 h-7 rounded-md",
          connected ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive")}>
          <GitBranch className="w-4 h-4" />
        </span>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm text-foreground truncate">{repo.repo_full_name}</span>
            <span className={cn("text-[10px] font-semibold px-1.5 py-0.5 rounded-full",
              connected ? "bg-success/15 text-success" : "bg-destructive/15 text-destructive")}>
              {connected ? "Connected" : "Failed"}
            </span>
          </div>
          {!connected && repo.last_error && (
            <p className="text-[11px] text-destructive/80 truncate">{repo.last_error}</p>
          )}
        </div>
        <button
          onClick={() => disconnectMut.mutate()}
          disabled={disconnectMut.isPending}
          className="ml-auto inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-destructive transition-colors"
        >
          <Unplug className="w-3.5 h-3.5" /> Disconnect
        </button>
      </div>

      {/* Master–detail */}
      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4">
        {/* PR list */}
        <Card className="h-fit lg:sticky lg:top-4">
          <div className="px-4 py-3 border-b border-border/60">
            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Pull requests
            </div>
          </div>
          <div className="max-h-[560px] overflow-y-auto">
            {isLoading ? (
              <div className="p-3 space-y-2">
                {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-16 w-full rounded-md" />)}
              </div>
            ) : !diffs?.diffs.length ? (
              <div className="px-4 py-10 text-center text-sm text-muted-foreground">
                No pull requests analyzed yet. Open a PR (or push) to the connected repo and Leaka
                will map its impact here.
              </div>
            ) : (
              <ul className="p-2 space-y-1">
                {diffs.diffs.map((d) => (
                  <PRListItem
                    key={d.id}
                    diff={d}
                    active={d.id === selectedDiff}
                    onClick={() => setSelectedDiff(d.id)}
                  />
                ))}
              </ul>
            )}
          </div>
        </Card>

        {/* Impact analysis */}
        <div>
          {selectedDiff == null ? (
            <Card>
              <CardContent className="py-20 text-center text-sm text-muted-foreground">
                Select a pull request to see its impact analysis.
              </CardContent>
            </Card>
          ) : (
            <ImpactPanel appId={appId} diffId={selectedDiff} />
          )}
        </div>
      </div>
    </div>
  );
}

function PRListItem({
  diff, active, onClick,
}: { diff: CodeDiffOut; active: boolean; onClick: () => void }) {
  const ingesting = diff.ingest_status === "pending";
  const failed = diff.ingest_status === "failed";
  return (
    <li>
      <button
        onClick={onClick}
        className={cn(
          "w-full text-left rounded-md border px-3 py-2.5 transition-colors",
          active
            ? "border-primary/50 bg-primary/5"
            : "border-transparent hover:border-border hover:bg-muted/30",
        )}
      >
        <div className="flex items-center gap-2">
          <GitPullRequest className={cn("w-3.5 h-3.5 shrink-0", active ? "text-primary" : "text-muted-foreground")} />
          <span className="text-xs font-semibold text-foreground">
            {diff.pr_number ? `PR #${diff.pr_number}` : diff.commit_sha ? `Commit ${diff.commit_sha.slice(0, 7)}` : `Diff ${diff.id}`}
          </span>
          <span className="ml-auto">
            {ingesting && <span className="text-[9px] text-muted-foreground inline-flex items-center gap-1"><CircleDashed className="w-3 h-3 animate-spin" />Analyzing</span>}
            {failed && <span className="text-[9px] text-destructive inline-flex items-center gap-1"><XCircle className="w-3 h-3" />Failed</span>}
            {!ingesting && !failed && <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/50" />}
          </span>
        </div>
        <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
          {diff.branch && (
            <span className="inline-flex items-center gap-1 font-mono truncate max-w-[140px]">
              <GitBranch className="w-3 h-3" />{diff.branch}
            </span>
          )}
          <span className="inline-flex items-center gap-1">
            <FileCode2 className="w-3 h-3" />{diff.changed_file_count} file{diff.changed_file_count === 1 ? "" : "s"}
          </span>
        </div>
      </button>
    </li>
  );
}

// ===========================================================================
// Impact analysis — the hero. Affected flows ranked by risk + explain chain +
// no-coverage warnings + the terminal "run recommended tests" action.
// ===========================================================================
function ImpactPanel({ appId, diffId }: { appId: number; diffId: number }) {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["diff-recommendation", appId, diffId],
    queryFn: () => api.getDiffRecommendation(appId, diffId),
    refetchInterval: (ctx) => (ctx.state.data?.status === "pending" ? 3000 : false),
  });

  const runMut = useMutation({
    mutationFn: () => api.runDiffRecommendation(appId, diffId),
    onSuccess: (res) =>
      toast({
        title: "Tests dispatched",
        description: `${res.job_ids.length} recommended test${res.job_ids.length === 1 ? "" : "s"} queued to run.`,
      }),
    onError: (e: Error) => toast({ title: "Could not run tests", description: e.message, variant: "destructive" }),
  });

  if (isLoading) return <Skeleton className="h-[520px] w-full rounded-lg" />;
  if (!data) return null;

  // Non-ok states — honest, never fabricated.
  if (data.status === "pending") {
    return (
      <StatePanel icon={<CircleDashed className="w-6 h-6 text-muted-foreground animate-spin" />}
        title="Analyzing this pull request…"
        body="Leaka is ingesting the diff and mapping it to your application graph. This refreshes automatically." />
    );
  }
  if (data.status === "failed") {
    return (
      <StatePanel icon={<XCircle className="w-6 h-6 text-destructive" />}
        title="Ingestion failed" tone="destructive"
        body={data.message} action={<Button size="sm" variant="outline" onClick={() => refetch()}>Retry</Button>} />
    );
  }
  if (data.status === "no_graph") {
    return (
      <StatePanel icon={<ShieldAlert className="w-6 h-6 text-amber-500" />}
        title="No application graph yet"
        body="Explore this application first so Leaka can map code changes to real flows. Until then, recommendations aren't available." />
    );
  }

  const mappings = data.mappings ?? [];
  const noCoverageCount = mappings.filter((m) => m.no_coverage_warning).length;
  const recCount = data.recommended_test_ids?.length ?? 0;

  if (mappings.length === 0) {
    return (
      <StatePanel icon={<ShieldCheck className="w-6 h-6 text-success" />}
        title="No mapped flows affected"
        body="None of the changed files mapped to a known flow in this application's graph. If that's unexpected, re-explore to refresh the graph." />
    );
  }

  return (
    <Card>
      <CardContent className="pt-5 pb-4">
        {/* Verdict headline */}
        <div className="flex items-start gap-3">
          <span className={cn("grid place-items-center w-9 h-9 rounded-lg shrink-0",
            noCoverageCount > 0 ? "bg-destructive/15 text-destructive" : "bg-success/15 text-success")}>
            {noCoverageCount > 0 ? <ShieldAlert className="w-5 h-5" /> : <ShieldCheck className="w-5 h-5" />}
          </span>
          <div className="min-w-0">
            <h3 className="text-base font-semibold tracking-tight">
              Affects {mappings.length} flow{mappings.length === 1 ? "" : "s"}
              {noCoverageCount > 0 && (
                <> — <span className="text-destructive">{noCoverageCount} with no coverage</span></>
              )}
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Impact derived from the changed files, mapped to your application graph and ranked by business risk.
            </p>
          </div>
        </div>

        {/* Affected flows */}
        <div className="mt-5 space-y-3">
          {mappings.map((m) => (
            <FlowImpactRow key={`${m.node_id}-${m.canonical_key}`} m={m} />
          ))}
        </div>
      </CardContent>

      {/* Terminal action bar */}
      <div className="flex items-center gap-3 border-t border-border/60 bg-muted/20 px-5 py-3">
        <div className="text-xs text-muted-foreground">
          {recCount > 0
            ? `${recCount} test${recCount === 1 ? "" : "s"} recommended for this change`
            : "No covering tests found for the affected flows"}
        </div>
        <Button
          size="sm"
          className="ml-auto"
          disabled={recCount === 0 || runMut.isPending}
          onClick={() => runMut.mutate()}
        >
          {runMut.isPending ? (
            <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />Dispatching…</>
          ) : (
            <><Play className="w-3.5 h-3.5 mr-1.5" />Run {recCount} recommended test{recCount === 1 ? "" : "s"}</>
          )}
        </Button>
      </div>
    </Card>
  );
}

function FlowImpactRow({ m }: { m: FlowMappingOut }) {
  const rc = riskClasses(m.risk_level);
  const cov = coverageMeta(m.coverage_state);
  const conf = Math.round((m.confidence || 0) * 100);

  return (
    <div className={cn("rounded-lg border bg-card/40 overflow-hidden", rc.border)}>
      {/* Header */}
      <div className="flex items-center gap-2 px-4 pt-3">
        <span className="text-sm font-semibold text-foreground truncate">{m.label || "Unknown flow"}</span>
        <span className={cn("text-[10px] font-bold px-1.5 py-0.5 rounded tabular-nums", rc.bg, rc.text)}>
          {m.risk_level}{m.risk_score ? ` · ${m.risk_score}` : ""}
        </span>
        <span className={cn("text-[10px] font-medium inline-flex items-center gap-1", cov.text)}>
          <span className={cn("w-1.5 h-1.5 rounded-full", cov.dot)} />{cov.label}
        </span>
        <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">{conf}% confidence</span>
      </div>

      {/* Explain chain: changed file → flow → covering test */}
      <div className="px-4 py-2.5">
        <ExplainChain m={m} />
      </div>

      {/* No-coverage warning — the killer signal */}
      {m.no_coverage_warning && (
        <div className="flex items-center gap-2 border-t border-destructive/20 bg-destructive/5 px-4 py-2">
          <ShieldAlert className="w-3.5 h-3.5 text-destructive shrink-0" />
          <span className="text-[11px] text-destructive/90">
            This change touches <span className="font-medium">{m.label}</span> but it has no test — a bug here would ship unnoticed.
          </span>
          <Button size="sm" variant="outline" className="ml-auto h-7 text-[11px] border-destructive/30 text-destructive hover:bg-destructive/10">
            <Sparkles className="w-3 h-3 mr-1" />Generate test
          </Button>
        </div>
      )}
    </div>
  );
}

// The reasoning breadcrumb: which changed file(s) → this flow → covering tests.
function ExplainChain({ m }: { m: FlowMappingOut }) {
  const files = filesFromSignals(m.signals);
  const testCount = m.recommended_test_ids?.length ?? 0;

  return (
    <div className="flex items-center gap-1.5 flex-wrap text-[11px]">
      {files.length > 0 ? (
        <span className="inline-flex items-center gap-1 font-mono px-1.5 py-0.5 rounded bg-muted text-foreground/80">
          <FileCode2 className="w-3 h-3" />{files[0]}
          {files.length > 1 && <span className="text-muted-foreground"> +{files.length - 1}</span>}
        </span>
      ) : (
        <span className="font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground">changed code</span>
      )}
      <ArrowRight className="w-3 h-3 text-muted-foreground/50" />
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-primary/10 text-primary">
        <GitCommitHorizontal className="w-3 h-3" />{m.label}
      </span>
      <ArrowRight className="w-3 h-3 text-muted-foreground/50" />
      {testCount > 0 ? (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-success/10 text-success">
          <ShieldCheck className="w-3 h-3" />{testCount} covering test{testCount === 1 ? "" : "s"}
        </span>
      ) : (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-destructive/10 text-destructive/90">
          <ShieldAlert className="w-3 h-3" />no test
        </span>
      )}
    </div>
  );
}

// Pull the changed file paths out of the mapping's explainable signals.
function filesFromSignals(signals: Record<string, unknown>[]): string[] {
  const out: string[] = [];
  for (const s of signals || []) {
    const detail = (s?.detail as Record<string, unknown>) || {};
    const f = detail.file;
    if (typeof f === "string" && !out.includes(f)) out.push(f);
  }
  return out;
}

function StatePanel({
  icon, title, body, action, tone,
}: {
  icon: React.ReactNode; title: string; body: string;
  action?: React.ReactNode; tone?: "destructive";
}) {
  return (
    <Card>
      <CardContent className="py-16 text-center space-y-3">
        <div className={cn("w-12 h-12 rounded-full mx-auto grid place-items-center",
          tone === "destructive" ? "bg-destructive/10" : "bg-muted")}>
          {icon}
        </div>
        <div className="font-medium">{title}</div>
        <p className="text-sm text-muted-foreground max-w-md mx-auto">{body}</p>
        {action && <div className="pt-1">{action}</div>}
      </CardContent>
    </Card>
  );
}
