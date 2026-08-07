"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api, type RunListEntry, type RunStatus } from "@/lib/api";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ArrowRight, Image, ListChecks, Sparkles } from "lucide-react";
import { formatDate, formatDuration } from "@/lib/utils";
import { useState } from "react";

const STATUS_OPTIONS: { label: string; value: RunStatus | "all" }[] = [
  { label: "All statuses", value: "all" },
  { label: "Pending", value: "pending" },
  { label: "Running", value: "running" },
  { label: "Passed", value: "completed" },
  { label: "Failed", value: "failed" },
  { label: "Cancelled", value: "cancelled" },
];

export default function RunsPage() {
  const [statusFilter, setStatusFilter] = useState<RunStatus | "all">("all");

  const { data, isLoading } = useQuery({
    queryKey: ["runs", statusFilter],
    queryFn: () =>
      api.listRuns({
        status: statusFilter === "all" ? undefined : statusFilter,
        limit: 100,
      }),
    refetchInterval: 5000, // keep refreshing so live runs update
  });

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">All Runs</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Full history of every QA run executed by the browser-use agent.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select
            value={statusFilter}
            onValueChange={(v) => setStatusFilter(v as RunStatus | "all")}
          >
            <SelectTrigger className="w-44">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button asChild>
            <Link href="/new">
              <Sparkles className="w-4 h-4 mr-2" />
              New run
            </Link>
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Run history</CardTitle>
          <CardDescription>
            Auto-refreshes every 5 seconds for live runs.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 8 }).map((_, i) => (
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
                        <div className="text-xs text-muted-foreground font-mono">
                          {r.job_id.slice(0, 12)}…
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
                        <span className="text-xs text-muted-foreground/60">—</span>
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

function EmptyRuns() {
  return (
    <div className="text-center py-10 space-y-3">
      <div className="w-12 h-12 rounded-full bg-muted mx-auto grid place-items-center">
        <ListChecks className="w-6 h-6 text-muted-foreground" />
      </div>
      <div className="font-medium">No runs match this filter</div>
      <p className="text-sm text-muted-foreground">
        Try a different status filter, or run a new test.
      </p>
      <Button asChild className="mt-2">
        <Link href="/new">
          <Sparkles className="w-4 h-4 mr-2" />
          Run a test
        </Link>
      </Button>
    </div>
  );
}
