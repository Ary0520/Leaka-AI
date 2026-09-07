"use client";

import { useQuery } from "@tanstack/react-query";
import { FolderGit2, CheckCircle2, XCircle, Clock } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import Link from "next/link";

import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";

export default function RunGroupsPage() {
  const { data: groups, isLoading } = useQuery({
    queryKey: ["run-groups"],
    queryFn: () => api.listRunGroups(),
    refetchInterval: 10000,
  });

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Pipeline Runs</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Aggregated executions of your test suites.
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : groups?.length === 0 ? (
        <Card className="border-dashed bg-muted/30">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
              <FolderGit2 className="h-6 w-6 text-primary" />
            </div>
            <h3 className="text-lg font-semibold mb-1">No pipeline runs yet</h3>
            <p className="text-sm text-muted-foreground max-w-sm">
              Trigger a test suite to see its aggregated execution results here.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {groups?.map((group) => {
            const passRate = Math.round((group.passed_runs / group.total_runs) * 100) || 0;
            const isFailed = group.failed_runs > 0;

            return (
              <Link key={group.id} href={`/runs?group=${group.id}`}>
                <Card className="hover:bg-muted/50 transition-colors border-l-4 overflow-hidden mb-4" style={{ borderLeftColor: isFailed ? "hsl(var(--destructive))" : "hsl(var(--success))" }}>
                  <CardContent className="p-4 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      {isFailed ? (
                        <XCircle className="h-5 w-5 text-destructive" />
                      ) : (
                        <CheckCircle2 className="h-5 w-5 text-success" />
                      )}
                      <div>
                        <div className="font-medium font-mono text-sm">
                          {group.id.slice(0, 8)}...{group.id.slice(-6)}
                        </div>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
                          <Clock className="h-3 w-3" />
                          {formatDistanceToNow(new Date(group.created_at), { addSuffix: true })}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-8">
                      <div className="text-center">
                        <div className="text-2xl font-semibold tabular-nums tracking-tight">
                          {passRate}%
                        </div>
                        <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
                          Pass Rate
                        </div>
                      </div>

                      <div className="flex gap-2">
                        <Badge variant="outline" className="bg-success/10 text-success border-success/20">
                          {group.passed_runs} passed
                        </Badge>
                        {group.failed_runs > 0 && (
                          <Badge variant="outline" className="bg-destructive/10 text-destructive border-destructive/20">
                            {group.failed_runs} failed
                          </Badge>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
