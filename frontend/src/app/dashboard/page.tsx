"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Sparkles, ArrowRight, Zap, CheckCircle2, XCircle, Activity, ShieldAlert, Bug, RefreshCcw } from "lucide-react";
import { toast } from "@/components/ui/use-toast";
import { cn } from "@/lib/utils";

function StatCard({
  label,
  value,
  tone = "default",
  description = "",
  icon: Icon
}: {
  label: string;
  value: number | string;
  tone?: "default" | "success" | "destructive" | "warn" | "info";
  description?: string;
  icon?: any;
}) {
  const toneCls =
    tone === "success" ? "text-emerald-400"
      : tone === "destructive" ? "text-rose-400"
        : tone === "warn" ? "text-emerald-400"
          : tone === "info" ? "text-blue-400"
            : "text-foreground";
  return (
    <Card className="border-0 bg-card">
      <CardContent className="pt-6 pb-6">
        <div className="flex items-center justify-between mb-2">
          <div className="text-[10px] text-muted-foreground uppercase tracking-widest font-semibold">{label}</div>
          {Icon && <Icon className="w-4 h-4 text-muted-foreground/50" />}
        </div>
        <div className={cn("text-3xl font-semibold tabular-nums tracking-tight", toneCls)}>{value}</div>
        {description && (
          <div className="text-[10px] text-muted-foreground mt-2">{description}</div>
        )}
      </CardContent>
    </Card>
  );
}

import { useWorkspace } from "@/app/providers";

export default function DashboardPage() {
  const { activeWorkspaceId } = useWorkspace();
  const { data: kpis, isLoading: kpisLoading } = useQuery({
    queryKey: ["dashboard-kpis", activeWorkspaceId],
    queryFn: () => api.dashboardKpis(activeWorkspaceId),
    refetchInterval: 15_000,
  });

  if (kpisLoading && !kpis) {
    return (
      <div className="p-8 space-y-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Skeleton className="h-32 rounded-xl bg-card" />
          <Skeleton className="h-32 rounded-xl bg-card" />
          <Skeleton className="h-32 rounded-xl bg-card" />
          <Skeleton className="h-32 rounded-xl bg-card" />
        </div>
      </div>
    );
  }

  const passRate = (kpis?.pass_rate != null) ? `${kpis.pass_rate}%` : "-";
  const passTone = kpis?.pass_rate && kpis.pass_rate > 80 ? "success" : "warn";

  return (
    <div className="p-8 max-w-[1400px] mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Analytics & Health</h1>
          <p className="text-sm text-muted-foreground mt-1">Live CI pipeline health and reliability metrics.</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" asChild>
            <Link href="/failures"><Bug className="w-4 h-4 mr-2" /> Triage Failures</Link>
          </Button>
          <Button asChild>
            <Link href="/new"><Sparkles className="w-4 h-4 mr-2" /> Run a new test</Link>
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          label="Total Runs" 
          value={kpis?.total_runs ?? 0} 
          tone="default"
          description="All time executions"
          icon={Activity}
        />
        <StatCard 
          label="Passed" 
          value={kpis?.passed_runs ?? 0} 
          tone="success"
          description="Successful workflows"
          icon={CheckCircle2}
        />
        <StatCard 
          label="Failed" 
          value={kpis?.failed_runs ?? 0} 
          tone="destructive"
          description="Failed workflows"
          icon={XCircle}
        />
        <StatCard 
          label="Pipeline Pass Rate" 
          value={passRate} 
          tone={passTone}
          description="All time average"
          icon={Activity}
        />
        <StatCard 
          label="Flake Rate" 
          value={`${kpis?.flake_rate ?? 0}%`} 
          tone="default"
          description="Runs marked flaky"
          icon={RefreshCcw}
        />
        <StatCard 
          label="Quarantined Tests" 
          value={kpis?.quarantined_tests ?? 0} 
          tone="info"
          description="Excluded from CI gates"
          icon={ShieldAlert}
        />
        <StatCard 
          label="Auto-healed Runs" 
          value={kpis?.auto_healed ?? 0} 
          tone="default"
          description="Failed runs healed by AI"
          icon={Zap}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border shadow-sm">
          <CardHeader>
            <CardTitle className="text-base font-medium">Top Failure Categories</CardTitle>
            <CardDescription>Most common root causes in the last 7 days</CardDescription>
          </CardHeader>
          <CardContent>
            {kpis?.failure_categories?.length === 0 ? (
              <div className="text-sm text-muted-foreground py-10 text-center">
                No categorized failures in the current window.
              </div>
            ) : (
              <div className="space-y-4">
                {kpis?.failure_categories?.map((f, i) => (
                  <div key={i} className="flex items-center justify-between p-3 rounded-lg border bg-card/50">
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-rose-500" />
                      <div className="font-medium text-sm">{f.category}</div>
                    </div>
                    <div className="font-mono text-sm">{f.count} runs</div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="border shadow-sm">
          <CardHeader>
            <CardTitle className="text-base font-medium">Pipeline Reliability</CardTitle>
            <CardDescription>Flaky tests over time (mocked for now)</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-sm text-muted-foreground py-10 text-center">
              Insufficient historical data to render reliability chart.
            </div>
          </CardContent>
        </Card>
      </div>

    </div>
  );
}
