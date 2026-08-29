"use client";

/**
 * HistoryTab — append-only snapshot timeline + a two-snapshot diff view.
 * Reads GET /snapshots and GET /snapshots/{a}/diff/{b}.
 */

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { History, GitCompare } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDate } from "@/lib/utils";

export function HistoryTab({ appId }: { appId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["app-snapshots", appId],
    queryFn: () => api.listSnapshots(appId, { limit: 50 }),
  });

  const [fromId, setFromId] = useState<number | null>(null);
  const [toId, setToId] = useState<number | null>(null);

  // Default: compare the two most recent snapshots.
  useEffect(() => {
    if (data?.snapshots?.length && fromId == null && toId == null) {
      const s = data.snapshots; // newest first
      if (s.length >= 2) { setFromId(s[1].id); setToId(s[0].id); }
      else { setToId(s[0].id); }
    }
  }, [data, fromId, toId]);

  const { data: diff } = useQuery({
    queryKey: ["snapshot-diff", appId, fromId, toId],
    queryFn: () => api.diffSnapshots(appId, fromId as number, toId as number),
    enabled: fromId != null && toId != null && fromId !== toId,
  });

  if (isLoading) return <Skeleton className="h-96 w-full rounded-lg" />;

  if (!data || data.total === 0) {
    return (
      <Card>
        <CardContent className="py-14 text-center space-y-2">
          <History className="w-8 h-8 text-muted-foreground mx-auto" />
          <div className="font-medium">No snapshots yet</div>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">
            Each exploration produces an immutable snapshot. Run an explore to start the history.
          </p>
        </CardContent>
      </Card>
    );
  }

  const diffCounts = (diff?.diff as { counts?: Record<string, number> } | undefined)?.counts;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* Timeline */}
      <Card className="lg:col-span-1">
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <History className="w-4 h-4 text-muted-foreground" /> Timeline
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {data.snapshots.map((s, idx) => {
            const summary = (s.diff_summary as { counts?: Record<string, number> } | null)?.counts;
            const isFrom = s.id === fromId;
            const isTo = s.id === toId;
            return (
              <button
                key={s.id}
                onClick={() => {
                  // Click to set the "to" (newer) then "from" (older).
                  if (toId == null || (fromId != null && toId != null)) { setToId(s.id); setFromId(null); }
                  else setFromId(s.id);
                }}
                className={cn(
                  "w-full text-left rounded-md border px-3 py-2.5 transition-colors",
                  isTo ? "border-primary/50 bg-primary/5" : isFrom ? "border-primary/30 bg-muted/40" : "border-border hover:border-primary/30",
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono text-muted-foreground">{formatDate(s.created_at)}</span>
                  {idx === 0 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary">Current</span>}
                </div>
                <div className="mt-1 text-sm">{s.node_count} nodes · {s.edge_count} edges</div>
                {summary && (
                  <div className="mt-1 text-[11px] font-mono text-muted-foreground">
                    +{summary.added ?? 0} · ~{summary.changed ?? 0} · −{summary.removed ?? 0}
                  </div>
                )}
              </button>
            );
          })}
          <p className="text-[11px] text-muted-foreground pt-1">
            Click two snapshots to compare them.
          </p>
        </CardContent>
      </Card>

      {/* Diff */}
      <Card className="lg:col-span-2">
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <GitCompare className="w-4 h-4 text-muted-foreground" /> Changes
          </CardTitle>
        </CardHeader>
        <CardContent>
          {fromId == null || toId == null || fromId === toId ? (
            <p className="text-sm text-muted-foreground py-8 text-center">
              Select two different snapshots on the left to see what changed.
            </p>
          ) : !diff ? (
            <Skeleton className="h-40 w-full" />
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <DiffStat label="Added" count={diffCounts?.added ?? 0} tone="success" />
                <DiffStat label="Changed" count={diffCounts?.changed ?? 0} tone="amber" />
                <DiffStat label="Removed" count={diffCounts?.removed ?? 0} tone="destructive" />
              </div>
              <DiffList title="Added flows" keys={(diff.diff as { added?: string[] }).added || []} tone="success" />
              <DiffList title="Changed flows" keys={(diff.diff as { changed?: string[] }).changed || []} tone="amber" />
              <DiffList title="Removed / staled" keys={(diff.diff as { removed?: string[] }).removed || []} tone="destructive" />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function DiffStat({ label, count, tone }: { label: string; count: number; tone: "success" | "amber" | "destructive" }) {
  const c = tone === "success" ? "text-success" : tone === "amber" ? "text-amber-500" : "text-destructive";
  return (
    <div className="rounded-md border border-border bg-muted/20 px-3 py-2 text-center">
      <div className={cn("text-2xl font-semibold", c)}>{count}</div>
      <div className="text-[11px] text-muted-foreground uppercase tracking-wide">{label}</div>
    </div>
  );
}

function DiffList({ title, keys, tone }: { title: string; keys: string[]; tone: "success" | "amber" | "destructive" }) {
  if (!keys.length) return null;
  const c = tone === "success" ? "text-success" : tone === "amber" ? "text-amber-500" : "text-destructive";
  return (
    <div>
      <div className="text-xs font-medium text-muted-foreground mb-1">{title}</div>
      <div className="flex flex-wrap gap-1.5">
        {keys.map((k) => (
          <span key={k} className={cn("text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted", c)}>{k.slice(0, 10)}</span>
        ))}
      </div>
    </div>
  );
}
