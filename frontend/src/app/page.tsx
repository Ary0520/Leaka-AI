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
