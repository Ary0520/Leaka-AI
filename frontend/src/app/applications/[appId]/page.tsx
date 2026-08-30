"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type AppMapNodeOut, type ExploreStatus } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ArrowLeft, Compass, Loader2, Play, Globe, FileText,
  ClipboardList, GitBranch, CheckCircle2, CircleDashed, Sparkles, XCircle,
  List, Network, TestTube2, History, Brain, GitPullRequest,
} from "lucide-react";
import { toast } from "@/components/ui/use-toast";
import { GraphTab } from "@/components/intelligence/graph-tab";
import { CoverageTab } from "@/components/intelligence/coverage-tab";
import { HistoryTab } from "@/components/intelligence/history-tab";
import { MemoryTab } from "@/components/intelligence/memory-tab";
import { PRIntelligenceTab } from "@/components/intelligence/pr-intelligence-tab";

const TERMINAL: ExploreStatus[] = ["completed", "failed", "cancelled"];

const NODE_ICON: Record<string, React.ReactNode> = {
  page: <FileText className="w-4 h-4" />,
  form: <ClipboardList className="w-4 h-4" />,
  flow: <GitBranch className="w-4 h-4" />,
};

export default function ApplicationDetailPage() {
  const params = useParams<{ appId: string }>();
  const appId = Number(params.appId);
  const router = useRouter();
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["app-map", appId],
    queryFn: () => api.getApplicationMap(appId),
    refetchInterval: (ctx) => {
      const s = ctx.state.data?.latest_explore?.status;
      if (s === "running" || s === "pending") return 3000;
      return false;
    },
  });

  const exploreMut = useMutation({
    mutationFn: () => api.exploreApplication(appId, 40),
    onSuccess: () => {
      toast({ title: "Exploration started", description: "Leaka is mapping your application…" });
      qc.invalidateQueries({ queryKey: ["app-map", appId] });
    },
    onError: (e: Error) =>
      toast({ title: "Could not start exploration", description: e.message, variant: "destructive" }),
  });

  const latest = data?.latest_explore;
  const isExploring = latest?.status === "running" || latest?.status === "pending";

  const generateTest = (node: AppMapNodeOut) => {
    // Pre-fill the New Test page from this discovered node
    const params = new URLSearchParams();
    params.set("prompt", node.suggested_prompt || `Test the "${node.label}" flow.`);
    if (node.url) params.set("target_url", node.url);
    params.set("name", node.label);
    router.push(`/new?${params.toString()}`);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 flex-wrap">
        <Button asChild variant="outline" size="sm">
          <Link href="/applications"><ArrowLeft className="w-4 h-4 mr-2" />Applications</Link>
        </Button>
        <h1 className="text-xl md:text-2xl font-semibold tracking-tight flex-1 truncate flex items-center gap-2">
          <Compass className="w-5 h-5 text-primary" />
          {isLoading ? <Skeleton className="h-6 w-48 inline-block" /> : data?.application.name}
        </h1>
        <Button disabled={exploreMut.isPending || isExploring} onClick={() => exploreMut.mutate()}>
          {exploreMut.isPending || isExploring ? (
            <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Exploring…</>
          ) : (
            <><Play className="w-4 h-4 mr-2" />{data?.total_nodes ? "Re-explore" : "Explore app"}</>
          )}
        </Button>
      </div>

      <Tabs defaultValue="graph" className="w-full">
        <TabsList>
          <TabsTrigger value="graph"><Network className="w-4 h-4 mr-1.5" />Graph</TabsTrigger>
          <TabsTrigger value="coverage"><TestTube2 className="w-4 h-4 mr-1.5" />Coverage</TabsTrigger>
          <TabsTrigger value="memory"><Brain className="w-4 h-4 mr-1.5" />Memory</TabsTrigger>
          <TabsTrigger value="pr"><GitPullRequest className="w-4 h-4 mr-1.5" />PR Intelligence</TabsTrigger>
          <TabsTrigger value="map"><List className="w-4 h-4 mr-1.5" />List</TabsTrigger>
          <TabsTrigger value="history"><History className="w-4 h-4 mr-1.5" />History</TabsTrigger>
        </TabsList>

        {/* ── Graph (React Flow node graph + risk/coverage) ── */}
        <TabsContent value="graph" className="mt-4">
          <GraphTab appId={appId} />
        </TabsContent>

        {/* ── Coverage (risk-weighted rollups + ranked gaps) ── */}
        <TabsContent value="coverage" className="mt-4">
          <CoverageTab appId={appId} />
        </TabsContent>

        {/* ── Memory ("what Leaka knows about this app") ── */}
        <TabsContent value="memory" className="mt-4">
          <MemoryTab appId={appId} />
        </TabsContent>

        {/* ── PR Intelligence (connect repo → per-PR affected flows + tests) ── */}
        <TabsContent value="pr" className="mt-4">
          <PRIntelligenceTab appId={appId} />
        </TabsContent>

        {/* ── History (append-only snapshots + diff) ── */}
        <TabsContent value="history" className="mt-4">
          <HistoryTab appId={appId} />
        </TabsContent>

        {/* ── Map (original flat discovered-map view, unchanged) ── */}
        <TabsContent value="map" className="mt-4 space-y-6">
      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : !data ? (
        <Alert variant="destructive"><AlertDescription>Application not found.</AlertDescription></Alert>
      ) : (
        <>
          {/* App info + coverage summary */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="md:col-span-2">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Globe className="w-4 h-4 text-primary" />
                  <a href={data.application.base_url} target="_blank" rel="noreferrer" className="underline truncate">
                    {data.application.base_url}
                  </a>
                </CardTitle>
                {data.application.description && (
                  <CardDescription>{data.application.description}</CardDescription>
                )}
              </CardHeader>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-xs text-muted-foreground uppercase tracking-wide">Coverage</div>
                <div className="mt-1 text-2xl font-semibold">
                  {data.total_nodes > 0
                    ? `${Math.round((data.covered_nodes / data.total_nodes) * 100)}%`
                    : "—"}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {data.covered_nodes} of {data.total_nodes} flows have tests
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Explore status banners */}
          {latest?.status === "running" && (
            <Alert className="bg-blue-500/10 border-blue-500/30 text-blue-700 dark:text-blue-300">
              <Loader2 className="w-4 h-4 animate-spin" />
              <AlertTitle>Exploring your application…</AlertTitle>
              <AlertDescription>
                Leaka is navigating the app and discovering flows. This updates every 3 seconds.
              </AlertDescription>
            </Alert>
          )}
          {latest?.status === "pending" && (
            <Alert>
              <CircleDashed className="w-4 h-4" />
              <AlertTitle>Exploration queued</AlertTitle>
              <AlertDescription>Starting shortly…</AlertDescription>
            </Alert>
          )}
          {latest?.status === "failed" && (
            <Alert variant="destructive">
              <XCircle className="w-4 h-4" />
              <AlertTitle>Exploration failed</AlertTitle>
              <AlertDescription>{latest.error_message || "The exploration run did not complete."}</AlertDescription>
            </Alert>
          )}
          {latest?.status === "completed" && latest.result_summary && (
            <Alert className="bg-emerald-500/10 border-emerald-500/40 text-emerald-700 dark:text-emerald-300">
              <CheckCircle2 className="w-4 h-4" />
              <AlertTitle>Exploration complete</AlertTitle>
              <AlertDescription>{latest.result_summary}</AlertDescription>
            </Alert>
          )}

          {/* Map nodes */}
          {data.nodes.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center space-y-3">
                <div className="w-12 h-12 rounded-full bg-muted mx-auto grid place-items-center">
                  <Compass className="w-6 h-6 text-muted-foreground" />
                </div>
                <div className="font-medium">No map yet</div>
                <p className="text-sm text-muted-foreground max-w-md mx-auto">
                  Run an exploration to discover this application&apos;s pages, forms, and flows.
                </p>
                {!isExploring && (
                  <Button className="mt-2" onClick={() => exploreMut.mutate()} disabled={exploreMut.isPending}>
                    <Play className="w-4 h-4 mr-2" />Explore now
                  </Button>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Discovered map</CardTitle>
                <CardDescription>
                  Pages, forms, and flows Leaka found. Green = has a test · Grey = untested.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {data.nodes.map((n) => (
                  <div
                    key={n.id}
                    className={
                      "flex items-start gap-3 rounded-md border px-3 py-2.5 " +
                      (n.is_covered ? "border-emerald-500/20 bg-emerald-500/5" : "border-border bg-muted/20")
                    }
                  >
                    <span className="text-muted-foreground mt-0.5 shrink-0">
                      {NODE_ICON[n.node_type] ?? <FileText className="w-4 h-4" />}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium">{n.label}</span>
                        <Badge variant="outline" className="text-[10px] capitalize">{n.node_type}</Badge>
                        {n.is_covered ? (
                          <Badge variant="secondary" className="text-[10px] text-emerald-600 dark:text-emerald-400">
                            <CheckCircle2 className="w-3 h-3 mr-1" />covered
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="text-[10px] text-muted-foreground">untested</Badge>
                        )}
                      </div>
                      {n.url && (
                        <div className="text-xs text-muted-foreground truncate mt-0.5 font-mono">{n.url}</div>
                      )}
                      {n.description && (
                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{n.description}</p>
                      )}
                    </div>
                    {!n.is_covered && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="shrink-0"
                        onClick={() => generateTest(n)}
                      >
                        <Sparkles className="w-3 h-3 mr-1" />Generate test
                      </Button>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </>
      )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
