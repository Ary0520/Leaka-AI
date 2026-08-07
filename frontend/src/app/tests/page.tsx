"use client";

import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api, type TestCaseOut, type RunListEntry } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { formatDate, truncate } from "@/lib/utils";
import { CheckCircle2, XCircle, Play, Plus, FileText, Clock, Loader2 } from "lucide-react";
import { toast } from "@/components/ui/use-toast";

function RunHistoryDots({ caseId }: { caseId: number }) {
  const { data } = useQuery({
    queryKey: ["case-runs", caseId],
    queryFn: () => api.listRuns({ test_case_id: caseId, limit: 8 }),
    staleTime: 30_000,
  });

  if (!data?.length) return <span className="text-xs text-muted-foreground/50">no runs</span>;

  return (
    <div className="flex items-center gap-1" title="Recent run history (newest right)">
      {[...data].reverse().map((r) => (
        <Link key={r.job_id} href={`/runs/${r.job_id}`}>
          <span
            title={`${r.status} · ${formatDate(r.created_at)}`}
            className={[
              "inline-block w-2.5 h-2.5 rounded-full transition-transform hover:scale-125",
              r.status === "completed" ? "bg-emerald-500"
                : r.status === "failed" ? "bg-destructive"
                  : r.status === "running" || r.status === "pending" ? "bg-blue-400 animate-pulse"
                    : "bg-muted-foreground/30",
            ].join(" ")}
          />
        </Link>
      ))}
    </div>
  );
}

export default function TestCasesPage() {
  const router = useRouter();
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["testcases-page"],
    queryFn: () => api.listTestCases({ limit: 200 }),
  });

  const runMut = useMutation({
    mutationFn: (c: TestCaseOut) => api.enqueueRun({
      name: c.name,
      prompt: c.prompt,
      target_url: c.target_url,
      success_criteria: c.success_criteria,
      test_case_id: c.id,
      use_vision: true,
      max_steps: 25,
    }),
    onSuccess: (r, c) => {
      toast({ title: "Run started", description: c.name });
      qc.invalidateQueries({ queryKey: ["case-runs", c.id] });
      router.push(`/runs/${r.job_id}`);
    },
    onError: (e: Error) => toast({ title: "Failed to start run", description: e.message, variant: "destructive" }),
  });

  const lastRunStatus = (runs: RunListEntry[] | undefined): "passed" | "failed" | "running" | "none" => {
    if (!runs?.length) return "none";
    const last = runs[0];
    if (last.status === "completed") return "passed";
    if (last.status === "failed") return "failed";
    if (last.status === "running" || last.status === "pending") return "running";
    return "none";
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Test Cases</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Reusable prompts you can run instantly or trigger from CI. History dots show recent pass/fail.
          </p>
        </div>
        <Button asChild>
          <Link href="/new"><Plus className="w-4 h-4 mr-2" />New case</Link>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">All cases</CardTitle>
          <CardDescription>
            Dots = recent run history (green = passed, red = failed, blue = running). Click any dot to open that run.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : !data?.length ? (
            <div className="text-center py-10 space-y-3">
              <div className="w-12 h-12 rounded-full bg-muted mx-auto grid place-items-center">
                <FileText className="w-6 h-6 text-muted-foreground" />
              </div>
              <div className="font-medium">No cases saved yet</div>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                Create a test case from the Run a Test screen to reuse it from the dashboard or CI.
              </p>
              <Button asChild className="mt-2"><Link href="/new">Create a case</Link></Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Prompt</TableHead>
                  <TableHead>Target URL</TableHead>
                  <TableHead>History</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="text-right">Run</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium text-sm max-w-[180px]">
                      <div className="truncate">{c.name}</div>
                      {c.suite_id && (
                        <Badge variant="outline" className="text-xs mt-0.5">Suite {c.suite_id}</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground max-w-xs truncate">
                      {truncate(c.prompt, 90)}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground max-w-[180px] truncate">
                      {c.target_url
                        ? <a href={c.target_url} target="_blank" rel="noreferrer" className="underline">{truncate(c.target_url, 35)}</a>
                        : "—"}
                    </TableCell>
                    <TableCell>
                      <RunHistoryDots caseId={c.id} />
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(c.updated_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        disabled={runMut.isPending && runMut.variables?.id === c.id}
                        onClick={() => runMut.mutate(c)}
                      >
                        {runMut.isPending && runMut.variables?.id === c.id
                          ? <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                          : <Play className="w-3 h-3 mr-1" />}
                        Run
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
