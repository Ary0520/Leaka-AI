"use client";

/**
 * CoverageTab — risk-weighted coverage rollups + a prioritized, risk-ranked
 * list of coverage gaps. Each gap has a one-click "Generate test" that routes
 * to /new pre-filled from the node's suggested prompt AND carries the real
 * GraphNode id so the created test records an authoritative coverage link.
 * Reads GET /coverage.
 */

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Sparkles, TestTube2 } from "lucide-react";
import { riskClasses, coverageMeta } from "@/lib/intelligence";
import { cn } from "@/lib/utils";
import { useState } from "react";
import { TestMatrixDialog } from "./test-matrix-dialog";

export function CoverageTab({ appId }: { appId: number }) {
  const router = useRouter();
  const { data, isLoading } = useQuery({
    queryKey: ["app-coverage", appId],
    queryFn: () => api.getApplicationCoverage(appId, { limit: 100 }),
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-40 w-full rounded-lg" />
        <Skeleton className="h-64 w-full rounded-lg" />
      </div>
    );
  }

  if (!data || data.is_empty) {
    return (
      <Card>
        <CardContent className="py-14 text-center space-y-2">
          <TestTube2 className="w-8 h-8 text-muted-foreground mx-auto" />
          <div className="font-medium">No coverage yet</div>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">
            Explore this application first — coverage is computed from its graph.
          </p>
        </CardContent>
      </Card>
    );
  }

  const [matrixOpen, setMatrixOpen] = useState(false);
  const [selectedGap, setSelectedGap] = useState<NonNullable<typeof data.gaps>[number] | null>(null);

  const generate = (gap: NonNullable<typeof data.gaps>[number]) => {
    setSelectedGap(gap);
    setMatrixOpen(true);
  };

  const app = data.application_rollup;

  return (
    <div className="space-y-6">
      {/* Rollups */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Coverage by category</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.category_rollups.length === 0 ? (
              <p className="text-sm text-muted-foreground">No categories yet.</p>
            ) : (
              data.category_rollups.map((r) => (
                <div key={r.scope}>
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="capitalize">{r.scope}</span>
                    <span className="font-mono text-muted-foreground">{Math.round(r.percent)}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className={cn("h-full rounded-full", r.percent >= 70 ? "bg-success" : r.percent >= 40 ? "bg-amber-500" : "bg-destructive/70")}
                      style={{ width: `${Math.min(100, r.percent)}%` }}
                    />
                  </div>
                  <div className="mt-1 text-[11px] text-muted-foreground">
                    {r.covered_count} covered · {r.partial_count} partial · {r.uncovered_count} uncovered
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Application</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-semibold tracking-tight">
              {app ? `${Math.round(app.percent)}%` : "—"}
            </div>
            <div className="text-xs text-muted-foreground mt-1">risk-weighted coverage</div>
            {app && (
              <div className="mt-3 text-[11px] text-muted-foreground">
                {app.covered_count} covered · {app.partial_count} partial · {app.uncovered_count} uncovered
                <br />across {app.node_count} flows
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Gaps */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Coverage gaps — ranked by risk</CardTitle>
        </CardHeader>
        <CardContent>
          {data.gaps.length === 0 ? (
            <p className="text-sm text-muted-foreground py-6 text-center">
              No gaps — every flow has coverage. 🎉
            </p>
          ) : (
            <div className="space-y-2">
              {data.gaps.map((g) => {
                const rc = riskClasses(g.risk_level);
                const cov = coverageMeta(g.state);
                return (
                  <div
                    key={g.node_id}
                    className="flex items-center gap-3 rounded-md border border-border bg-muted/20 px-3 py-2.5"
                  >
                    <span className={cn("w-2 h-2 rounded-full shrink-0", rc.dot)} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium">{g.label}</span>
                        <span className={cn("text-[10px] font-semibold px-1.5 py-0.5 rounded", rc.bg, rc.text)}>
                          {g.risk_level}
                        </span>
                        <span className={cn("text-[10px]", cov.text)}>{cov.label}</span>
                        {g.business_category && (
                          <span className="text-[10px] text-muted-foreground">· {g.business_category}</span>
                        )}
                      </div>
                      {g.url && <div className="text-[11px] font-mono text-muted-foreground truncate mt-0.5">{g.url}</div>}
                    </div>
                    <Button size="sm" variant="outline" className="shrink-0" onClick={() => generate(g)}>
                      <Sparkles className="w-3.5 h-3.5 mr-1" /> Generate test
                    </Button>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
      <TestMatrixDialog
        appId={appId}
        open={matrixOpen}
        onOpenChange={setMatrixOpen}
        graphNodeId={selectedGap?.node_id}
        nodeLabel={selectedGap?.label}
      />
    </div>
  );
}
