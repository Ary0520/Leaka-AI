"use client";

/**
 * NodeDetailSheet — right-side slide-over showing a graph node's full detail:
 * semantics, an explainable RISK factor breakdown (horizontal bars), the
 * COVERAGE verdict with evidence, a MEMORY summary, provenance, and a manual
 * OVERRIDE control. Reads GET /graph/nodes/{id}; overrides via PATCH.
 *
 * Built with framer-motion (already a dependency) as a themed drawer so we
 * don't add a new UI primitive. Fully theme-token styled.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { api, type GraphNodeOverride } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { X, ShieldAlert, TestTube2, Brain, GitBranch, Pencil, Check } from "lucide-react";
import { riskClasses, coverageMeta, nodeTypeLabel } from "@/lib/intelligence";
import { cn } from "@/lib/utils";
import { toast } from "@/components/ui/use-toast";

type RiskFactor = { name: string; contribution: number; weight: number; evidence?: Record<string, unknown> };

export function NodeDetailSheet({
  appId,
  nodeId,
  onClose,
}: {
  appId: number;
  nodeId: number | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [ov, setOv] = useState<GraphNodeOverride>({});

  const { data: node, isLoading } = useQuery({
    queryKey: ["graph-node", appId, nodeId],
    queryFn: () => api.getGraphNode(appId, nodeId as number),
    enabled: nodeId != null,
  });

  const overrideMut = useMutation({
    mutationFn: () => api.overrideGraphNode(appId, nodeId as number, ov),
    onSuccess: () => {
      toast({ title: "Override saved", description: "Your correction is now authoritative." });
      qc.invalidateQueries({ queryKey: ["graph-node", appId, nodeId] });
      qc.invalidateQueries({ queryKey: ["app-graph", appId] });
      setEditing(false);
      setOv({});
    },
    onError: (e: Error) => toast({ title: "Override failed", description: e.message, variant: "destructive" }),
  });

  const risk = (node?.risk as { level?: string; score?: number; source?: string; factors?: RiskFactor[] } | null) || null;
  const rc = riskClasses(risk?.level);

  return (
    <AnimatePresence>
      {nodeId != null && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-background/60 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="fixed right-0 top-0 z-50 h-full w-full max-w-md border-l border-border bg-card overflow-y-auto"
          >
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-card px-5 py-4">
              <span className="text-[10px] font-mono uppercase tracking-wide text-muted-foreground">
                Node · {node ? nodeTypeLabel(node.node_type) : "…"}
              </span>
              <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
                <X className="w-4 h-4" />
              </button>
            </div>

            {isLoading || !node ? (
              <div className="p-5 space-y-4">
                <Skeleton className="h-8 w-2/3" />
                <Skeleton className="h-24 w-full" />
                <Skeleton className="h-24 w-full" />
              </div>
            ) : (
              <div className="p-5 space-y-6">
                {/* Header */}
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <h2 className="text-xl font-semibold tracking-tight">{node.label}</h2>
                    <span className={cn("text-xs font-semibold px-2 py-1 rounded shrink-0", rc.bg, rc.text)}>
                      {risk?.level || "Trivial"} {risk?.score != null && `· ${risk.score}`}
                    </span>
                  </div>
                  {node.url_pattern && (
                    <div className="mt-1 text-xs font-mono text-muted-foreground">{node.url_pattern}</div>
                  )}
                  <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{node.business_category ? node.business_category : "uncategorized"}</span>
                    <span>·</span>
                    <span>role: {node.role_association || "unknown"}</span>
                    {node.status === "stale" && <span className="text-amber-500">· stale</span>}
                  </div>
                </div>

                {/* Risk factors */}
                <Section icon={<ShieldAlert className="w-4 h-4" />} title="Risk explanation">
                  {risk?.factors?.length ? (
                    <div className="space-y-2.5">
                      {risk.factors
                        .filter((f) => f.name !== "manual_override")
                        .map((f) => {
                          const pct = f.weight > 0 ? Math.round((f.contribution / f.weight) * 100) : 0;
                          return (
                            <div key={f.name}>
                              <div className="flex items-center justify-between text-xs mb-1">
                                <span className="text-muted-foreground capitalize">
                                  {f.name.replace(/_/g, " ")}
                                </span>
                                <span className="font-mono text-foreground">
                                  {f.contribution.toFixed(0)}/{f.weight.toFixed(0)}
                                </span>
                              </div>
                              <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                                <div
                                  className="h-full bg-primary/70 rounded-full"
                                  style={{ width: `${Math.min(100, pct)}%` }}
                                />
                              </div>
                            </div>
                          );
                        })}
                      {risk.source === "manual_override" && (
                        <p className="text-[11px] text-amber-500">Risk manually overridden — factors shown for reference.</p>
                      )}
                    </div>
                  ) : (
                    <Empty>Risk not yet computed for this node.</Empty>
                  )}
                </Section>

                {/* Coverage */}
                <Section icon={<TestTube2 className="w-4 h-4" />} title="Coverage verdict">
                  <CoverageBlock coverage={node.coverage as Record<string, unknown> | null} />
                </Section>

                {/* Memory */}
                <Section icon={<Brain className="w-4 h-4" />} title="What Leaka learned">
                  {node.memory ? (
                    <pre className="text-[11px] text-muted-foreground whitespace-pre-wrap font-mono">
                      {JSON.stringify(node.memory, null, 2)}
                    </pre>
                  ) : (
                    <Empty>No learned memory for this node yet.</Empty>
                  )}
                </Section>

                {/* Provenance */}
                <Section icon={<GitBranch className="w-4 h-4" />} title="Provenance">
                  <div className="text-xs text-muted-foreground space-y-1">
                    <div>First seen: run #{node.first_seen_run ?? "—"}</div>
                    <div>Last seen: run #{node.last_seen_run ?? "—"}</div>
                  </div>
                </Section>

                {/* Override */}
                <Section icon={<Pencil className="w-4 h-4" />} title="Manual override">
                  {!editing ? (
                    <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
                      <Pencil className="w-3.5 h-3.5 mr-2" /> Correct type / category / role / risk
                    </Button>
                  ) : (
                    <div className="space-y-3">
                      <OverrideRow label="Type">
                        <Select onValueChange={(v) => setOv((o) => ({ ...o, node_type: v }))}>
                          <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="unchanged" /></SelectTrigger>
                          <SelectContent>
                            {["page", "form", "flow", "action", "role"].map((t) => (
                              <SelectItem key={t} value={t}>{t}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </OverrideRow>
                      <OverrideRow label="Category">
                        <Select onValueChange={(v) => setOv((o) => ({ ...o, business_category: v }))}>
                          <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="unchanged" /></SelectTrigger>
                          <SelectContent>
                            {["billing", "checkout", "auth", "account", "onboarding", "search", "navigation", "content", "unknown"].map((c) => (
                              <SelectItem key={c} value={c}>{c}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </OverrideRow>
                      <OverrideRow label="Risk level">
                        <Select onValueChange={(v) => setOv((o) => ({ ...o, risk: { level: v } }))}>
                          <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="unchanged" /></SelectTrigger>
                          <SelectContent>
                            {["Critical", "High", "Medium", "Low", "Trivial"].map((r) => (
                              <SelectItem key={r} value={r}>{r}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </OverrideRow>
                      <div className="flex gap-2 pt-1">
                        <Button size="sm" disabled={overrideMut.isPending || Object.keys(ov).length === 0}
                          onClick={() => overrideMut.mutate()}>
                          <Check className="w-3.5 h-3.5 mr-1" /> Save override
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => { setEditing(false); setOv({}); }}>Cancel</Button>
                      </div>
                    </div>
                  )}
                </Section>
              </div>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-2 text-sm font-medium text-foreground">
        <span className="text-muted-foreground">{icon}</span>
        {title}
      </div>
      {children}
    </div>
  );
}

function OverrideRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-muted-foreground w-20 shrink-0">{label}</span>
      <div className="flex-1">{children}</div>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-xs text-muted-foreground italic">{children}</p>;
}

function CoverageBlock({ coverage }: { coverage: Record<string, unknown> | null }) {
  // The node-detail endpoint returns coverage as a placeholder (null) until the
  // coverage engine has run for this node; show an honest state.
  if (!coverage) {
    return <Empty>Coverage not yet computed — check the Coverage tab.</Empty>;
  }
  const state = (coverage.state as string) || "undetermined";
  const cov = coverageMeta(state);
  return (
    <div className={cn("rounded-md px-3 py-2 text-xs", cov.bg)}>
      <span className={cn("font-medium", cov.text)}>{cov.label}</span>
    </div>
  );
}
