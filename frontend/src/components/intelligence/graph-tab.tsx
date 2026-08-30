"use client";

/**
 * GraphTab — the "Graph" view of an application: a coverage summary strip,
 * the interactive React Flow graph, and the node detail slide-over.
 * Reads GET /graph and GET /coverage (for the summary numbers).
 */

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { api, type CoverageResponse } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { NodeDetailSheet } from "./node-detail-sheet";
import { InsightRibbon } from "./insight-ribbon";
import { Compass, ShieldAlert, TestTube2, Network } from "lucide-react";

// Lazy-load the graph canvas (React Flow + ELK.js are heavy + client-only).
// This keeps the app-detail route lean and only pays the cost when the Graph
// tab is actually rendered.
const GraphCanvas = dynamic(
  () => import("./graph-canvas").then((m) => m.GraphCanvas),
  {
    ssr: false,
    loading: () => <Skeleton className="h-[680px] w-full rounded-xl" />,
  },
);

export function GraphTab({ appId }: { appId: number }) {
  const [selected, setSelected] = useState<number | null>(null);
  const router = useRouter();

  const { data: graph, isLoading } = useQuery({
    queryKey: ["app-graph", appId],
    queryFn: () => api.getApplicationGraph(appId, { limit: 500 }),
  });
  const { data: coverage } = useQuery({
    queryKey: ["app-coverage", appId],
    queryFn: () => api.getApplicationCoverage(appId, { limit: 100 }),
  });

  const generateFromGap = (gap: NonNullable<CoverageResponse["gaps"]>[number]) => {
    const params = new URLSearchParams();
    params.set("prompt", gap.suggested_prompt || `Test the "${gap.label}" flow.`);
    if (gap.url) params.set("target_url", gap.url);
    params.set("name", gap.label);
    params.set("app_id", String(appId));
    params.set("node_id", String(gap.node_id));
    router.push(`/new?${params.toString()}`);
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-lg" />)}
        </div>
        <Skeleton className="h-[640px] w-full rounded-lg" />
      </div>
    );
  }

  if (!graph || graph.is_empty) {
    return (
      <Card>
        <CardContent className="py-14 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-muted mx-auto grid place-items-center">
            <Compass className="w-6 h-6 text-muted-foreground" />
          </div>
          <div className="font-medium">No graph yet</div>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">
            Run an exploration to build the application graph — Leaka will map pages,
            flows, and forms, then score their business risk and coverage.
          </p>
        </CardContent>
      </Card>
    );
  }

  const rollup = coverage?.application_rollup;
  const critical = coverage?.gaps?.filter((g) => g.risk_level === "Critical").length ?? 0;

  const stats = [
    { label: "Risk-weighted coverage", value: rollup ? `${Math.round(rollup.percent)}%` : "—", icon: TestTube2 },
    { label: "Flows discovered", value: String(graph.total_nodes), icon: Network },
    { label: "Critical gaps", value: String(critical), icon: ShieldAlert, alert: critical > 0 },
    { label: "Relationships", value: String(graph.total_edges), icon: Compass },
  ];

  return (
    <div className="space-y-4">
      {/* The "aha" — lead with the single most important insight. */}
      <InsightRibbon
        graph={graph}
        coverage={coverage}
        onFocus={setSelected}
        onGenerate={generateFromGap}
      />

      {/* Summary strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {stats.map((s) => {
          const Icon = s.icon;
          return (
            <Card key={s.label}>
              <CardContent className="pt-5">
                <div className="flex items-center gap-2 text-xs text-muted-foreground uppercase tracking-wide">
                  <Icon className="w-3.5 h-3.5" /> {s.label}
                </div>
                <div className={"mt-2 text-3xl font-semibold tracking-tight" + (s.alert ? " text-destructive" : "")}>
                  {s.value}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Graph */}
      <GraphCanvas
        nodes={graph.nodes}
        edges={graph.edges}
        selectedId={selected}
        onSelect={setSelected}
      />
      <p className="text-xs text-muted-foreground">
        Click a node to see its blast radius — the downstream flows that break if it does —
        plus its risk breakdown, coverage evidence, and what Leaka has learned. The legend
        is bottom-right.
      </p>

      <NodeDetailSheet appId={appId} nodeId={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
