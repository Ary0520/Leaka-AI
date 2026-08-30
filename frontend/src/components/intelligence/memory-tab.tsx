"use client";

/**
 * MemoryTab — "What Leaka knows about this app" (R5.10, Task 22).
 *
 * Surfaces the durable, per-application knowledge Leaka has learned, grouped by
 * kind, in a human-readable form:
 *   - locator      → the preferred element locators that worked (ranked)
 *   - auth_pattern → the shape of a login that cleared the gate (never secrets)
 *   - timing       → observed durations (how long flows take)
 *   - outcome      → historical pass/fail per node (feeds risk)
 *   - fingerprint  → versioned node identity signals
 *
 * Read-only + owner-scoped (the endpoint enforces tenant isolation). This is the
 * "compounding moat" made visible: it fills up and gets richer every run.
 */

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type MemoryItemOut } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Brain, MousePointerClick, KeyRound, Timer, CheckCircle2, XCircle, Fingerprint } from "lucide-react";
import { cn } from "@/lib/utils";

const KIND_META: Record<string, { label: string; icon: React.ComponentType<{ className?: string }>; blurb: string }> = {
  locator: { label: "Element locators", icon: MousePointerClick, blurb: "Selectors that reliably found elements — reused to act faster and reduce flakiness." },
  auth_pattern: { label: "Auth patterns", icon: KeyRound, blurb: "How logins cleared the gate (never credentials) — reused to reach authenticated areas." },
  timing: { label: "Timing", icon: Timer, blurb: "Observed durations — so the agent waits the right amount, not too little." },
  outcome: { label: "Outcomes", icon: CheckCircle2, blurb: "Historical pass/fail per flow — feeds risk so failing areas rank higher." },
  fingerprint: { label: "Fingerprints", icon: Fingerprint, blurb: "Versioned identity signals per node — the self-healing seed." },
};

const KIND_ORDER = ["locator", "auth_pattern", "timing", "outcome", "fingerprint"];

export function MemoryTab({ appId }: { appId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["app-memory", appId],
    queryFn: () => api.getApplicationMemory(appId, { limit: 300 }),
  });

  const grouped = useMemo(() => {
    const g: Record<string, MemoryItemOut[]> = {};
    for (const it of data?.items ?? []) {
      (g[it.kind] ??= []).push(it);
    }
    return g;
  }, [data]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full rounded-lg" />
        <Skeleton className="h-64 w-full rounded-lg" />
      </div>
    );
  }

  const total = data?.total ?? 0;

  if (!data || total === 0) {
    return (
      <Card>
        <CardContent className="py-14 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-muted mx-auto grid place-items-center">
            <Brain className="w-6 h-6 text-muted-foreground" />
          </div>
          <div className="font-medium">Leaka hasn&apos;t learned anything yet</div>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">
            As you explore this app and run tests, Leaka records what it learns — the
            locators that worked, how long flows take, how login clears, and pass/fail
            history. That knowledge shows up here and makes every future run faster and
            more reliable.
          </p>
        </CardContent>
      </Card>
    );
  }

  const presentKinds = KIND_ORDER.filter((k) => (grouped[k]?.length ?? 0) > 0);
  const otherKinds = Object.keys(grouped).filter((k) => !KIND_ORDER.includes(k));

  return (
    <div className="space-y-4">
      {/* Header summary */}
      <Card>
        <CardContent className="pt-5">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Brain className="w-4 h-4 text-primary" />
            What Leaka knows about this app
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {total} learned item{total === 1 ? "" : "s"} across {presentKinds.length + otherKinds.length} categor
            {presentKinds.length + otherKinds.length === 1 ? "y" : "ies"}. This grows every run.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {[...presentKinds, ...otherKinds].map((k) => {
              const meta = KIND_META[k];
              const Icon = meta?.icon ?? Brain;
              return (
                <Badge key={k} variant="outline" className="gap-1.5">
                  <Icon className="w-3 h-3" />
                  {(meta?.label ?? k)} · {grouped[k].length}
                </Badge>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Grouped sections */}
      {[...presentKinds, ...otherKinds].map((kind) => (
        <MemorySection key={kind} kind={kind} items={grouped[kind]} />
      ))}
    </div>
  );
}

function MemorySection({ kind, items }: { kind: string; items: MemoryItemOut[] }) {
  const meta = KIND_META[kind];
  const Icon = meta?.icon ?? Brain;
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Icon className="w-4 h-4 text-primary" />
          {meta?.label ?? kind}
          <span className="text-xs font-normal text-muted-foreground">({items.length})</span>
        </CardTitle>
        {meta?.blurb && <p className="text-xs text-muted-foreground">{meta.blurb}</p>}
      </CardHeader>
      <CardContent className="space-y-2">
        {items.slice(0, 40).map((it) => (
          <MemoryRow key={it.id} item={it} />
        ))}
        {items.length > 40 && (
          <p className="text-xs text-muted-foreground italic">+ {items.length - 40} more…</p>
        )}
      </CardContent>
    </Card>
  );
}

function MemoryRow({ item }: { item: MemoryItemOut }) {
  const p = item.payload || {};
  return (
    <div className="rounded-md border border-border bg-muted/20 px-3 py-2 text-sm">
      {item.kind === "locator" && <LocatorRow p={p} />}
      {item.kind === "auth_pattern" && <AuthRow p={p} />}
      {item.kind === "timing" && <TimingRow p={p} />}
      {item.kind === "outcome" && <OutcomeRow p={p} />}
      {item.kind === "fingerprint" && <FingerprintRow p={p} version={item.version} />}
      {!KIND_ORDER.includes(item.kind) && (
        <pre className="text-[11px] text-muted-foreground whitespace-pre-wrap font-mono">
          {JSON.stringify(p, null, 2)}
        </pre>
      )}
    </div>
  );
}

function LocatorRow({ p }: { p: Record<string, unknown> }) {
  const selector = (p.selector as string) || "";
  const text = (p.element_text as string) || "";
  const hierarchy = Array.isArray(p.hierarchy) ? (p.hierarchy as { strategy?: string }[]) : [];
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-2 flex-wrap">
        <code className="text-xs font-mono text-foreground truncate">{selector}</code>
        {text && <span className="text-xs text-muted-foreground truncate">“{text}”</span>}
      </div>
      {hierarchy.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1">
          {hierarchy.map((h, i) => (
            <span
              key={i}
              className={cn(
                "text-[10px] px-1.5 py-0.5 rounded",
                i === 0 ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground",
              )}
            >
              {h.strategy}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function AuthRow({ p }: { p: Record<string, unknown> }) {
  const summary = (p.summary as string) || (p.pattern as string) || "Login pattern learned";
  return (
    <div className="flex items-center gap-2">
      <KeyRound className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
      <span className="text-xs text-foreground">{summary}</span>
    </div>
  );
}

function TimingRow({ p }: { p: Record<string, unknown> }) {
  const ms = Number(p.ms || 0);
  const secs = ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
  return (
    <div className="flex items-center gap-2">
      <Timer className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
      <span className="text-xs text-foreground">Observed ~{secs}</span>
    </div>
  );
}

function OutcomeRow({ p }: { p: Record<string, unknown> }) {
  const passed = p.passed === true;
  const dur = Number(p.duration_seconds || 0);
  return (
    <div className="flex items-center gap-2">
      {passed ? (
        <CheckCircle2 className="w-3.5 h-3.5 text-success shrink-0" />
      ) : (
        <XCircle className="w-3.5 h-3.5 text-destructive shrink-0" />
      )}
      <span className={cn("text-xs", passed ? "text-success" : "text-destructive")}>
        {passed ? "Passed" : "Failed"}
      </span>
      {dur > 0 && <span className="text-xs text-muted-foreground">· {dur}s</span>}
    </div>
  );
}

function FingerprintRow({ p, version }: { p: Record<string, unknown>; version: number }) {
  const label = (p.label as string) || (p.url_signature as string) || "node fingerprint";
  return (
    <div className="flex items-center gap-2">
      <Fingerprint className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
      <span className="text-xs text-foreground truncate">{label}</span>
      <Badge variant="outline" className="text-[10px]">v{version}</Badge>
    </div>
  );
}
