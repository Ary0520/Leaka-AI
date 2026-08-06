"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api, type RunListEntry } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Sparkles, ArrowRight, Image, ListChecks } from "lucide-react";
import { formatDate, formatDuration, truncate, cn } from "@/lib/utils";

export default function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.listRuns({ limit: 50 }),
  });

  const stats = getStats(data || []);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Recent QA runs, status at a glance.
          </p>
        </div>
        <Button asChild>
          <Link href="/new">
            <Sparkles className="w-4 h-4 mr-2" />
            Run a new test
          </Link>
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard
          label="Total runs"
          value={stats.total}
          icon={<ListChecks className="w-5 h-5" />}
        />
        <StatCard
          label="Passed"
          value={stats.passed}
          tone="success"
          icon={<CheckIcon />}
        />
        <StatCard
          label="Failed"
          value={stats.failed}
          tone="destructive"
          icon={<FailIcon />}
        />
        <StatCard
          label="In progress"
          value={stats.inProgress}
          tone="info"
          icon={<Loader />}
        />
      </div>

      {/* Runs table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">Recent runs</CardTitle>
              <CardDescription>
                Runs are executed asynchronously by the browser-use agent.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full rounded" />
              ))}
            </div>
          ) : !data?.length ? (
            <EmptyRuns />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Test</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Proof</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((r) => (
                  <TableRow key={r.job_id}>
                    <TableCell>
                      <div>
                        <div className="font-medium text-sm">{r.name}</div>
                        <div className="text-xs text-muted-foreground truncate max-w-md">
                          {r.job_id}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={r.status} />
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDuration(r.duration_seconds)}
                    </TableCell>
                    <TableCell>
                      {r.has_visual_proof ? (
                        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                          <Image className="w-3 h-3" /> Screenshot
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground/60">
                          —
                        </span>
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

function StatCard({
  label,
  value,
  tone = "default",
  icon,
}: {
  label: string;
  value: number;
  tone?: "default" | "success" | "destructive" | "info";
  icon?: React.ReactNode;
}) {
  const toneCls =
    tone === "success"
      ? "text-emerald-600 dark:text-emerald-400"
      : tone === "destructive"
        ? "text-destructive"
        : tone === "info"
          ? "text-blue-600 dark:text-blue-400"
          : "text-primary";
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wide">
              {label}
            </div>
            <div className={cn("text-3xl font-semibold mt-1", toneCls)}>
              {value}
            </div>
          </div>
          <div
            className={cn(
              "w-9 h-9 rounded-md grid place-items-center bg-muted/50",
              toneCls,
            )}
          >
            {icon}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function CheckIcon() {
  return <span className="text-emerald-500">✓</span>;
}
function FailIcon() {
  return <span className="text-destructive">✗</span>;
}
function Loader() {
  return <span>⟳</span>;
}

function getStats(runs: RunListEntry[]) {
  const total = runs.length;
  const passed = runs.filter((r) => r.status === "completed").length;
  const failed = runs.filter((r) => r.status === "failed").length;
  const inProgress = runs.filter(
    (r) => r.status === "running" || r.status === "pending",
  ).length;
  return { total, passed, failed, inProgress };
}

function EmptyRuns() {
  return (
    <div className="text-center py-10 space-y-3">
      <div className="w-12 h-12 rounded-full bg-muted mx-auto grid place-items-center">
        <ListChecks className="w-6 h-6 text-muted-foreground" />
      </div>
      <div className="font-medium">No runs yet</div>
      <p className="text-sm text-muted-foreground max-w-md mx-auto">
        Run your first natural-language QA test. The browser-use agent will
        execute it headlessly and store the results.
      </p>
      <Button asChild className="mt-2">
        <Link href="/new">
          <Sparkles className="w-4 h-4 mr-2" />
          Create your first run
        </Link>
      </Button>
    </div>
  );
}
