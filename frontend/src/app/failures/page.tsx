"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Bug } from "lucide-react";
import { api } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { Skeleton } from "@/components/ui/skeleton";

export default function FailuresPage() {
  const { data: kpis, isLoading } = useQuery({
    queryKey: ["dashboard-kpis"],
    queryFn: () => api.dashboardKpis(),
  });

  if (isLoading) return <div className="p-8"><Skeleton className="h-64 w-full bg-card" /></div>;

  return (
    <div className="p-8 max-w-[1400px] mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Failure Analysis</h1>
        <p className="text-sm text-muted-foreground mt-1">Review and triage test failures to maintain pipeline health.</p>
      </div>

      <Card className="border shadow-sm">
        <CardHeader>
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <Bug className="w-4 h-4" /> Top Failure Categories
          </CardTitle>
          <CardDescription>Failures in the last 7 days grouped by root cause.</CardDescription>
        </CardHeader>
        <CardContent>
          {kpis?.failure_categories?.length === 0 ? (
            <div className="text-sm text-muted-foreground py-10 text-center">
              No categorized failures in the current window.
            </div>
          ) : (
            <div className="space-y-4">
              {kpis?.failure_categories?.map((f, i) => (
                <div key={i} className="flex items-center justify-between p-4 rounded-lg border bg-card/50">
                  <div className="font-medium">{f.category}</div>
                  <div className="font-mono text-sm">{f.count} runs</div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
