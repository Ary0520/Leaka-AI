"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, type RunListEntry } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Sparkles, ArrowRight, Image, ListChecks, Zap, CheckCircle2, XCircle, Activity } from "lucide-react";
import { toast } from "@/components/ui/use-toast";
import { formatDate, formatDuration, truncate, cn } from "@/lib/utils";

// ── Health Grid ───────────────────────────────────────────────────────────────

type HealthRow = Awaited<ReturnType<typeof api.dashboardHealth>>[number];
type RunCell = HealthRow["runs"][number];

function cellColor(run: RunCell): string {
  if (run.status === "running" || run.status === "pending")
    return "bg-blue-400 animate-pulse";
  if (run.is_successful === true) return "bg-emerald-500";
  if (run.is_successful === false || run.status === "failed") return "bg-destructive";
  return "bg-muted-foreground/20";
}

function HealthStatusDot({ row }: { row: HealthRow }) {
  if (!row.total_runs) return <span className="w-2 h-2 rounded-full bg-muted-foreground/20 inline-block" />;
  if (row.last_successful === true) return <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />;
  if (row.last_successful === false) return <span className="w-2 h-2 rounded-full bg-destructive inline-block" />;
  return <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse inline-block" />;
}

function PassRateBadge({ rate }: { rate: number | null }) {
  if (rate === null) return <span className="text-xs text-muted-foreground">—</span>;
  const color = rate >= 90 ? "text-emerald-600 dark:text-emerald-400"
    : rate >= 70 ? "text-yellow-600 dark:text-yellow-400"
      : "text-destructive";
  return <span className={cn("text-xs font-mono font-medium tabular-nums", color)}>{rate}%</span>;
}

function HealthGrid({ data }: { data: HealthRow[] }) {
  const CELLS = 14;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <CardTitle className="text-lg flex items-center gap-2">
              <Activity className="w-5 h-5 text-primary" />
              Revenue flow health
            </CardTitle>
            <CardDescription className="mt-1">
              Last {CELLS} runs per test. Green = pass · Red = fail · Grey = no run. Click any cell to inspect.
            </CardDescription>
          </div>
          <Button asChild size="sm" variant="outline">
            <Link href="/tests">Manage test cases</Link>
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <div className="text-sm text-muted-foreground py-6 text-center">
            No test cases yet. Create a test case and run it to see health data here.
          </div>
        ) : (
          <div className="space-y-3">
            {data.map((row) => {
              // Pad left with empty slots so newest run is always rightmost
              const padCount = Math.max(0, CELLS - row.runs.length);
              return (
                <div key={row.id} className="flex items-center gap-3">
                  {/* Status dot + name */}
                  <div className="flex items-center gap-2 w-52 shrink-0">
                    <HealthStatusDot row={row} />
                    <Link
                      href={`/tests`}
                      className="text-sm font-medium truncate hover:underline"
                      title={row.name}
                    >
                      {row.name}
                    </Link>
                  </div>

                  {/* Run cells */}
                  <div className="flex items-center gap-1 flex-1">
                    {/* Empty padding cells */}
                    {Array.from({ length: padCount }).map((_, i) => (
                      <div
                        key={`pad-${i}`}
                        className="w-5 h-5 rounded-sm bg-muted/40 shrink-0"
                      />
                    ))}
                    {/* Run cells */}
                    {row.runs.map((run) => (
                      <Link
                        key={run.job_id}
                        href={`/runs/${run.job_id}`}
                        title={`${run.status} · ${run.created_at ? new Date(run.created_at).toLocaleString() : ""} · ${run.duration_seconds ?? 0}s`}
                        className={cn(
                          "w-5 h-5 rounded-sm shrink-0 transition-all hover:scale-125 hover:ring-2 hover:ring-offset-1 hover:ring-ring",
                          cellColor(run),
                        )}
                      />
                    ))}
                  </div>

                  {/* Pass rate */}
                  <div className="w-10 text-right shrink-0">
                    <PassRateBadge rate={row.pass_rate} />
                  </div>
                </div>
              );
            })}

            {/* Legend */}
            <div className="flex items-center gap-4 pt-2 border-t text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-emerald-500 inline-block" /> Pass
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-destructive inline-block" /> Fail
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-blue-400 inline-block" /> Running
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-muted-foreground/20 inline-block" /> No run
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Main Dashboard ────────────────────────────────────────────────────────────

function getStats(runs: RunListEntry[]) {
  const total = runs.length;
  const passed = runs.filter((r) => r.status === "completed").length;
  const failed = runs.filter((r) => r.status === "failed").length;
  const inProgress = runs.filter((r) => r.status === "running" || r.status === "pending").length;
  return { total, passed, failed, inProgress };
}

export default function DashboardPage() {
  const qc = useQueryClient();

  const { data: runs, isLoading: runsLoading } = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.listRuns({ limit: 30 }),
    refetchInterval: 10_000,
  });

  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ["dashboard-health"],
    queryFn: () => api.dashboardHealth(14),
    refetchInterval: 15_000,
  });

  const seedMut = useMutation({
    mutationFn: () => api.seedDemo(),
    onSuccess: (r) => {
      toast({ title: r.created > 0 ? "Demo data loaded" : "Already seeded", description: r.message });
      qc.invalidateQueries({ queryKey: ["runs"] });
      qc.invalidateQueries({ queryKey: ["dashboard-health"] });
      qc.invalidateQueries({ queryKey: ["testcases-page"] });
    },
    onError: (e: Error) => toast({ title: "Seed failed", description: e.message, variant: "destructive" }),
  });

  const stats = getStats(runs || []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Revenue flow health at a glance.
          </p>
        </div>
        <Button asChild>
          <Link href="/new">
            <Sparkles className="w-4 h-4 mr-2" />
            Run a new test
          </Link>
        </Button>
      </div>

      {/* Stats bar — compact, not hero */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Total runs" value={stats.total} tone="default" />
        <StatCard label="Passed" value={stats.passed} tone="success" />
        <StatCard label="Failed" value={stats.failed} tone="destructive" />
        <StatCard
          label="Pass rate"
          value={stats.total > 0 ? `${Math.round((stats.passed / stats.total) * 100)}%` : "—"}
          tone={stats.total === 0 ? "default" : stats.passed / stats.total >= 0.9 ? "success" : stats.passed / stats.total >= 0.7 ? "warn" : "destructive"}
        />
      </div>

      {/* Health grid — the hero */}
      {healthLoading ? (
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-4 w-64 mt-1" />
          </CardHeader>
          <CardContent className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-7 w-full" />
            ))}
          </CardContent>
        </Card>
      ) : (
        <HealthGrid data={health || []} />
      )}

      {/* Recent runs table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">Recent runs</CardTitle>
              <CardDescription>Latest 30 runs across all test cases.</CardDescription>
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link href="/runs">View all <ArrowRight className="w-3 h-3 ml-1" /></Link>
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {runsLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full rounded" />
              ))}
            </div>
          ) : !runs?.length ? (
            <EmptyRuns onSeed={() => seedMut.mutate()} isSeeding={seedMut.isPending} />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Test</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Visual proof</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((r) => (
                  <TableRow key={r.job_id}>
                    <TableCell>
                      <div className="font-medium text-sm">{r.name}</div>
                      <div className="text-xs text-muted-foreground font-mono">{r.job_id.slice(0, 10)}…</div>
                    </TableCell>
                    <TableCell><StatusBadge status={r.status} /></TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDuration(r.duration_seconds)}
                    </TableCell>
                    <TableCell>
                      {r.has_visual_proof ? (
                        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                          <Image className="w-3 h-3" /> Screenshot
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground/50">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(r.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button asChild size="sm" variant="outline">
                        <Link href={`/runs/${r.job_id}`}>
                          View <ArrowRight className="w-3 h-3 ml-1" />
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ── Helper components ─────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: number | string;
  tone?: "default" | "success" | "destructive" | "warn" | "info";
}) {
  const toneCls =
    tone === "success" ? "text-emerald-600 dark:text-emerald-400"
      : tone === "destructive" ? "text-destructive"
        : tone === "warn" ? "text-yellow-600 dark:text-yellow-400"
          : tone === "info" ? "text-blue-600 dark:text-blue-400"
            : "text-foreground";
  return (
    <Card>
      <CardContent className="pt-5 pb-4">
        <div className="text-xs text-muted-foreground uppercase tracking-wide mb-1">{label}</div>
        <div className={cn("text-2xl font-semibold tabular-nums", toneCls)}>{value}</div>
      </CardContent>
    </Card>
  );
}

function EmptyRuns({ onSeed, isSeeding }: { onSeed: () => void; isSeeding: boolean }) {
  return (
    <div className="text-center py-10 space-y-3">
      <div className="w-12 h-12 rounded-full bg-muted mx-auto grid place-items-center">
        <ListChecks className="w-6 h-6 text-muted-foreground" />
      </div>
      <div className="font-medium">No runs yet</div>
      <p className="text-sm text-muted-foreground max-w-md mx-auto">
        Run your first natural-language QA test, or load example test cases to explore the platform.
      </p>
      <div className="flex items-center justify-center gap-3 mt-2 flex-wrap">
        <Button asChild>
          <Link href="/new">
            <Sparkles className="w-4 h-4 mr-2" />
            Create your first run
          </Link>
        </Button>
        <Button variant="outline" onClick={onSeed} disabled={isSeeding}>
          {isSeeding ? (
            <><span className="w-4 h-4 mr-2 border-2 border-current border-t-transparent rounded-full animate-spin inline-block" />Loading…</>
          ) : (
            <><Zap className="w-4 h-4 mr-2" />Load demo cases</>
          )}
        </Button>
      </div>
    </div>
  );
}
