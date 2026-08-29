"use client";

/**
 * InsightRibbon — the "aha" banner that leads the Graph tab with the SINGLE
 * most important thing a QA lead needs to know, in plain English:
 *
 *   "⚠ Checkout is Critical and untested — 3 flows depend on it."
 *
 * It derives that insight deterministically from the coverage gaps (highest
 * risk, uncovered/partial) + the graph edges (how many nodes depend on it),
 * and offers a one-click jump to that node (opens its detail). If everything
 * is healthy, it shows a calm "all clear" state instead of alarming the user.
 *
 * Presentational: it takes the already-fetched graph + coverage data and an
 * onFocus callback; owns no fetching.
 */

import type { GraphResponse, CoverageResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ShieldAlert, ArrowRight, CheckCircle2, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

const RISK_ORDER: Record<string, number> = {
  Critical: 5, High: 4, Medium: 3, Low: 2, Trivial: 1,
};

export function InsightRibbon({
  graph,
  coverage,
  onFocus,
  onGenerate,
}: {
  graph: GraphResponse;
  coverage?: CoverageResponse;
  onFocus: (nodeId: number) => void;
  onGenerate?: (gap: NonNullable<CoverageResponse["gaps"]>[number]) => void;
}) {
  const gaps = coverage?.gaps ?? [];

  // The headline gap: highest risk, then most dependents, then lowest coverage.
  // Count dependents from depends_on edges pointing AT each gap node.
  const dependentsByNode = new Map<number, number>();
  for (const e of graph.edges) {
    if (e.edge_type === "depends_on") {
      dependentsByNode.set(e.target_node_id, (dependentsByNode.get(e.target_node_id) ?? 0) + 1);
    }
  }

  const ranked = [...gaps].sort((a, b) => {
    const r = (RISK_ORDER[b.risk_level] ?? 0) - (RISK_ORDER[a.risk_level] ?? 0);
    if (r !== 0) return r;
    const d = (dependentsByNode.get(b.node_id) ?? 0) - (dependentsByNode.get(a.node_id) ?? 0);
    if (d !== 0) return d;
    return a.canonical_key.localeCompare(b.canonical_key);
  });

  const top = ranked[0];

  // ── Healthy state: no gaps at all ──────────────────────────────────────
  if (!top) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-success/30 bg-success/5 px-4 py-3">
        <CheckCircle2 className="w-5 h-5 text-success shrink-0" />
        <div className="text-sm">
          <span className="font-medium text-foreground">Every discovered flow has coverage.</span>{" "}
          <span className="text-muted-foreground">
            No critical gaps right now — nice. Re-explore after shipping to keep this current.
          </span>
        </div>
      </div>
    );
  }

  // ── The headline gap ───────────────────────────────────────────────────
  const deps = dependentsByNode.get(top.node_id) ?? 0;
  const isCriticalish = top.risk_level === "Critical" || top.risk_level === "High";
  const stateWord = top.state === "partially_covered" ? "only partially tested" : "untested";

  return (
    <div
      className={cn(
        "flex flex-col md:flex-row md:items-center gap-3 rounded-xl border px-4 py-3.5",
        isCriticalish ? "border-destructive/40 bg-destructive/5" : "border-amber-500/30 bg-amber-500/5",
      )}
    >
      <div className={cn("shrink-0 grid place-items-center w-9 h-9 rounded-lg",
        isCriticalish ? "bg-destructive/15 text-destructive" : "bg-amber-500/15 text-amber-500")}>
        <ShieldAlert className="w-5 h-5" />
      </div>

      <div className="min-w-0 flex-1">
        <div className="text-sm text-foreground">
          <span className={cn("font-semibold", isCriticalish ? "text-destructive" : "text-amber-500")}>
            {top.label}
          </span>{" "}
          is <span className="font-medium">{top.risk_level}</span> risk and {stateWord}
          {deps > 0 && (
            <>
              {" "}—{" "}
              <span className="font-medium">
                {deps} flow{deps === 1 ? "" : "s"} depend{deps === 1 ? "s" : ""} on it
              </span>
            </>
          )}
          .
        </div>
        <div className="text-xs text-muted-foreground mt-0.5">
          {deps > 0
            ? "If this breaks, everything that depends on it breaks too. Cover it first."
            : "This is your highest-priority coverage gap right now."}
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {onGenerate && (
          <Button size="sm" onClick={() => onGenerate(top)}>
            <Sparkles className="w-3.5 h-3.5 mr-1.5" /> Generate test
          </Button>
        )}
        <Button size="sm" variant="outline" onClick={() => onFocus(top.node_id)}>
          Inspect <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
        </Button>
      </div>
    </div>
  );
}
