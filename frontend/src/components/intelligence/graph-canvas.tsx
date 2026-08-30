"use client";

/**
 * GraphCanvas — the flagship Application Graph.
 *
 * Architecture (the professional pattern, per React Flow's official ELK example):
 *     backend graph  →  ELK.js layered layout  →  React Flow render
 * ELK computes a deterministic LEFT→RIGHT dependency layout (entry points on
 * the left, the flows everything depends on cascading right), and React Flow
 * draws it as an n8n-style canvas: bold ported node cards with risk color +
 * glow, thick smooth connectors, `depends_on` edges visually distinct from
 * `navigates_to`.
 *
 * Props contract is unchanged ({nodes, edges, selectedId, onSelect}) so the
 * parent tab needs no changes. Themed with the app's semantic tokens.
 */

import { useEffect, useMemo, useState, useCallback } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  Panel,
  type Node,
  type Edge,
  type NodeProps,
  Handle,
  Position,
  BackgroundVariant,
  MarkerType,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import ELK from "elkjs/lib/elk.bundled.js";
import { FileText, ClipboardList, GitBranch, Zap, UserCircle } from "lucide-react";
import type { GraphNodeOut, GraphEdgeOut } from "@/lib/api";
import { riskClasses, coverageMeta, nodeTypeLabel } from "@/lib/intelligence";
import { cn } from "@/lib/utils";

const NODE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  page: FileText,
  form: ClipboardList,
  flow: GitBranch,
  action: Zap,
  role: UserCircle,
};

const elk = new ELK();

const NODE_W = 244;
const NODE_H = 108;

// ELK layered layout, left→right — the n8n / workflow look.
const ELK_OPTIONS = {
  "elk.algorithm": "layered",
  "elk.direction": "RIGHT",
  "elk.layered.spacing.nodeNodeBetweenLayers": "110",
  "elk.spacing.nodeNode": "60",
  "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
  "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
  "elk.edgeRouting": "SPLINES",
};

// ---------------------------------------------------------------------------
// Custom node — bold, ported, risk-colored (n8n-style)
// ---------------------------------------------------------------------------
type NodeData = {
  node: GraphNodeOut;
  selected?: boolean;
  // Blast-radius focus states (set while a node is selected):
  impacted?: boolean;   // this node is a transitive dependent of the selection
  dimmed?: boolean;     // not the selection and not in its blast radius
};

function AppGraphNode({ data }: NodeProps) {
  const d = data as unknown as NodeData;
  const n = d.node;
  const risk = (n.risk as { level?: string; score?: number } | null) || null;
  const level = risk?.level || "Trivial";
  const rc = riskClasses(level);
  const cov = coverageMeta(n.coverage_state ?? undefined);
  const stale = n.status === "stale";
  const critical = level === "Critical" || level === "High";

  const Icon = NODE_ICONS[(n.node_type || "page").toLowerCase()] || FileText;

  return (
    <div
      style={{ width: NODE_W }}
      className={cn(
        "group relative rounded-xl border bg-card text-left overflow-hidden transition-all duration-200",
        rc.border,
        d.selected
          ? "ring-2 ring-primary shadow-lg shadow-primary/10"
          : "hover:-translate-y-0.5 hover:shadow-lg hover:border-primary/50",
        // Blast-radius focus: impacted dependents get a warning ring; unrelated
        // nodes fade back so the impact path is unmistakable.
        d.impacted && "ring-2 ring-destructive/70 shadow-lg shadow-destructive/10",
        d.dimmed && "opacity-25 saturate-50",
        stale && "opacity-45 border-dashed",
      )}
    >
      {/* Risk accent bar down the left edge */}
      <div className={cn("absolute left-0 top-0 h-full w-1", rc.dot)} />
      {/* Critical/High ambient glow */}
      {critical && !stale && !d.dimmed && (
        <div className={cn("absolute -inset-1 rounded-xl opacity-30 blur-lg -z-10", rc.dot)} />
      )}
      {/* Blast-radius badge on impacted dependents */}
      {d.impacted && (
        <div className="absolute -top-2 -right-2 z-10 text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-destructive text-destructive-foreground shadow">
          at risk
        </div>
      )}

      {/* Ports */}
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-background !border-2 !border-muted-foreground/60 !-left-1.5"
      />

      <div className="pl-4 pr-3 pt-2.5 pb-2">
        {/* Header: icon + type + risk chip */}
        <div className="flex items-center gap-2">
          <span className={cn("grid place-items-center w-6 h-6 rounded-md shrink-0", rc.bg, rc.text)}>
            <Icon className="w-3.5 h-3.5" />
          </span>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">
            {nodeTypeLabel(n.node_type)}
          </span>
          <span className={cn("ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded tabular-nums", rc.bg, rc.text)}>
            {level}{risk?.score != null ? ` · ${risk.score}` : ""}
          </span>
        </div>

        {/* Title */}
        <div className="mt-1.5 text-sm font-semibold text-foreground leading-snug truncate">
          {n.label || "Untitled"}
        </div>
        {n.url_pattern && (
          <div className="text-[10px] font-mono text-muted-foreground/70 truncate">{n.url_pattern}</div>
        )}
      </div>

      {/* Footer: coverage + category, on a subtle divider */}
      <div className="flex items-center gap-1.5 border-t border-border/60 bg-muted/20 pl-4 pr-3 py-1.5">
        <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", cov.dot)} />
        <span className={cn("text-[10px] font-medium", cov.text)}>{cov.label}</span>
        {n.business_category && (
          <span className="ml-auto text-[10px] text-muted-foreground capitalize truncate max-w-[90px]">
            {n.business_category}
          </span>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="!w-3 !h-3 !bg-background !border-2 !border-muted-foreground/60 !-right-1.5"
      />
    </div>
  );
}

const nodeTypes = { app: AppGraphNode };

// ---------------------------------------------------------------------------
// Blast radius — "if this node breaks, what else breaks?"
// An edge  A --depends_on--> B  means A depends on B, so if B breaks, A breaks.
// The blast radius of a selected node S is therefore every node that can REACH
// S through depends_on / part_of_flow edges (S's transitive dependents). Pure,
// deterministic BFS over the reverse dependency edges. Returns the set of node
// ids in the blast radius (excluding S itself) plus the edge ids that connect
// them, so the canvas can highlight the impact path and dim everything else.
// ---------------------------------------------------------------------------
const _IMPACT_EDGE_TYPES = new Set(["depends_on", "part_of_flow"]);

function computeBlastRadius(
  selectedId: number,
  edges: GraphEdgeOut[],
): { nodeIds: Set<number>; edgeIds: Set<number> } {
  // Reverse adjacency: for each dependency target B, who depends on it (sources)?
  const dependentsOf = new Map<number, { node: number; edgeId: number }[]>();
  for (const e of edges) {
    if (!_IMPACT_EDGE_TYPES.has(e.edge_type)) continue;
    const arr = dependentsOf.get(e.target_node_id) ?? [];
    arr.push({ node: e.source_node_id, edgeId: e.id });
    dependentsOf.set(e.target_node_id, arr);
  }

  const impactedNodes = new Set<number>();
  const impactedEdges = new Set<number>();
  const queue: number[] = [selectedId];
  const visited = new Set<number>([selectedId]);

  while (queue.length) {
    const cur = queue.shift() as number;
    for (const { node, edgeId } of dependentsOf.get(cur) ?? []) {
      impactedEdges.add(edgeId);
      if (!visited.has(node)) {
        visited.add(node);
        impactedNodes.add(node);
        queue.push(node);
      }
    }
  }
  return { nodeIds: impactedNodes, edgeIds: impactedEdges };
}

// ---------------------------------------------------------------------------
// Edge styling — depends_on is the important structural signal.
// ---------------------------------------------------------------------------
function edgeStyle(
  edgeType: string,
  stale: boolean,
): { style: React.CSSProperties; animated: boolean; markerColor: string } {
  const muted = stale;
  if (edgeType === "depends_on") {
    const color = muted ? "hsl(var(--destructive) / 0.2)" : "hsl(var(--destructive) / 0.55)";
    return {
      animated: !muted,
      style: { stroke: color, strokeWidth: 2, strokeDasharray: muted ? "4 4" : undefined },
      markerColor: color,
    };
  }
  if (edgeType === "part_of_flow") {
    const color = "hsl(var(--primary) / 0.5)";
    return {
      animated: false,
      style: { stroke: color, strokeWidth: 2, strokeDasharray: "6 3" },
      markerColor: color,
    };
  }
  // navigates_to
  const color = muted ? "hsl(var(--muted-foreground) / 0.15)" : "hsl(var(--muted-foreground) / 0.55)";
  return {
    animated: false,
    style: { stroke: color, strokeWidth: 1.5, strokeDasharray: muted ? "4 4" : undefined },
    markerColor: color,
  };
}

// ---------------------------------------------------------------------------
// Inner flow (needs ReactFlowProvider for fitView after async layout)
// ---------------------------------------------------------------------------
function Flow({
  nodes: gNodes,
  edges: gEdges,
  selectedId,
  onSelect,
}: {
  nodes: GraphNodeOut[];
  edges: GraphEdgeOut[];
  selectedId?: number | null;
  onSelect: (id: number) => void;
}) {
  const [rfNodes, setRfNodes] = useState<Node[]>([]);
  const [rfEdges, setRfEdges] = useState<Edge[]>([]);
  const { fitView } = useReactFlow();

  // Base (unpositioned) elements from backend data.
  const baseNodes: Node[] = useMemo(
    () =>
      gNodes.map((n) => ({
        id: String(n.id),
        type: "app",
        position: { x: 0, y: 0 },
        data: { node: n } as unknown as Record<string, unknown>,
        width: NODE_W,
        height: NODE_H,
      })),
    [gNodes],
  );

  const baseEdges: Edge[] = useMemo(
    () =>
      gEdges.map((e) => {
        const st = edgeStyle(e.edge_type, e.status === "stale");
        return {
          id: String(e.id),
          source: String(e.source_node_id),
          target: String(e.target_node_id),
          type: "smoothstep",
          animated: st.animated,
          style: st.style,
          // Directional arrowhead — the signature that makes the canvas read as
          // a workflow flow rather than an undirected web.
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 18,
            height: 18,
            color: st.markerColor,
          },
          label: e.edge_type === "depends_on" ? "depends on" : undefined,
          labelStyle: { fill: "hsl(var(--muted-foreground))", fontSize: 9, fontWeight: 600 },
          labelBgStyle: { fill: "hsl(var(--card))", fillOpacity: 0.9 },
        };
      }),
    [gEdges],
  );

  // Run ELK layout whenever the data changes.
  useEffect(() => {
    let cancelled = false;
    if (!baseNodes.length) {
      setRfNodes([]);
      setRfEdges([]);
      return;
    }
    const graph = {
      id: "root",
      layoutOptions: ELK_OPTIONS,
      children: baseNodes.map((n) => ({ id: n.id, width: NODE_W, height: NODE_H })),
      edges: baseEdges.map((e) => ({ id: e.id, sources: [e.source], targets: [e.target] })),
    };
    elk
      .layout(graph as never)
      .then((res: { children?: { id: string; x?: number; y?: number }[] }) => {
        if (cancelled) return;
        const posById = new Map((res.children || []).map((c) => [c.id, { x: c.x ?? 0, y: c.y ?? 0 }]));
        setRfNodes(
          baseNodes.map((n) => ({
            ...n,
            position: posById.get(n.id) || { x: 0, y: 0 },
            targetPosition: Position.Left,
            sourcePosition: Position.Right,
          })),
        );
        setRfEdges(baseEdges);
        // Fit after the DOM paints the new positions.
        requestAnimationFrame(() => fitView({ padding: 0.18, duration: 400 }));
      })
      .catch(() => {
        // Fallback: no layout → stack them so the canvas is never blank.
        setRfNodes(baseNodes.map((n, i) => ({ ...n, position: { x: 0, y: i * (NODE_H + 24) } })));
        setRfEdges(baseEdges);
      });
    return () => {
      cancelled = true;
    };
  }, [baseNodes, baseEdges, fitView]);

  // Blast radius for the currently-selected node (its transitive dependents).
  const blast = useMemo(() => {
    if (selectedId == null) return { nodeIds: new Set<number>(), edgeIds: new Set<number>() };
    return computeBlastRadius(selectedId, gEdges);
  }, [selectedId, gEdges]);

  const focusActive = selectedId != null;
  const selectedLabel = useMemo(
    () => gNodes.find((n) => n.id === selectedId)?.label || "This flow",
    [gNodes, selectedId],
  );

  // Reflect selection + blast-radius focus into node data.
  const decoratedNodes = useMemo(
    () =>
      rfNodes.map((n) => {
        const id = Number(n.id);
        const isSelected = id === selectedId;
        const isImpacted = blast.nodeIds.has(id);
        return {
          ...n,
          data: {
            ...(n.data as object),
            selected: isSelected,
            impacted: focusActive && isImpacted,
            dimmed: focusActive && !isSelected && !isImpacted,
          },
        };
      }),
    [rfNodes, selectedId, blast, focusActive],
  );

  // Reflect blast-radius focus into edges: impact-path edges brighten, others
  // fade, so the "if this breaks, these break" chain stands out.
  const decoratedEdges = useMemo(() => {
    if (!focusActive) return rfEdges;
    return rfEdges.map((e) => {
      const onImpactPath = blast.edgeIds.has(Number(e.id));
      if (onImpactPath) {
        return {
          ...e,
          animated: true,
          style: {
            ...(e.style as React.CSSProperties),
            stroke: "hsl(var(--destructive) / 0.85)",
            strokeWidth: 2.5,
            opacity: 1,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 18,
            height: 18,
            color: "hsl(var(--destructive) / 0.85)",
          },
          zIndex: 10,
        };
      }
      return {
        ...e,
        animated: false,
        style: { ...(e.style as React.CSSProperties), opacity: 0.12 },
      };
    });
  }, [rfEdges, blast, focusActive]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => onSelect(Number(node.id)),
    [onSelect],
  );

  return (
    <ReactFlow
      nodes={decoratedNodes}
      edges={decoratedEdges}
      nodeTypes={nodeTypes}
      onNodeClick={handleNodeClick}
      fitView
      minZoom={0.15}
      maxZoom={1.6}
      proOptions={{ hideAttribution: true }}
      nodesDraggable
      nodesConnectable={false}
      elementsSelectable
      defaultEdgeOptions={{ type: "smoothstep" }}
    >
      <Background variant={BackgroundVariant.Dots} gap={22} size={1.5} color="hsl(var(--border))" />

      {/* Blast-radius banner — the enterprise "if this breaks, what breaks?" answer */}
      {focusActive && (
        <Panel position="top-center">
          <div className="pointer-events-none flex items-center gap-2 rounded-full border border-border bg-card/95 px-3 py-1.5 shadow-md backdrop-blur">
            {blast.nodeIds.size > 0 ? (
              <>
                <span className="w-2 h-2 rounded-full bg-destructive animate-pulse" />
                <span className="text-xs text-foreground">
                  <span className="font-semibold text-destructive">{selectedLabel}</span> impacts{" "}
                  <span className="font-semibold">{blast.nodeIds.size}</span> downstream flow
                  {blast.nodeIds.size === 1 ? "" : "s"} if it breaks
                </span>
              </>
            ) : (
              <>
                <span className="w-2 h-2 rounded-full bg-muted-foreground/50" />
                <span className="text-xs text-muted-foreground">
                  Nothing else depends on <span className="font-medium text-foreground">{selectedLabel}</span> —
                  isolated flow
                </span>
              </>
            )}
          </div>
        </Panel>
      )}

      {/* Legend — self-explanatory visual language (risk + edge types) */}
      <Panel position="bottom-right">
        <div className="rounded-lg border border-border bg-card/95 px-3 py-2 shadow-md backdrop-blur text-[10px] space-y-1.5">
          <div className="font-semibold text-muted-foreground uppercase tracking-wide text-[9px]">Risk</div>
          <div className="flex items-center gap-3">
            <LegendDot className="bg-destructive" label="Critical / High" />
            <LegendDot className="bg-amber-500" label="Medium" />
            <LegendDot className="bg-muted-foreground/50" label="Low / Trivial" />
          </div>
          <div className="font-semibold text-muted-foreground uppercase tracking-wide text-[9px] pt-1">Relationships</div>
          <div className="flex items-center gap-3 flex-wrap">
            <LegendLine className="bg-destructive/60" label="depends on" />
            <LegendLine className="border-t border-dashed border-primary/60" label="part of flow" dashed />
            <LegendLine className="bg-muted-foreground/50" label="navigates to" />
          </div>
        </div>
      </Panel>

      <Controls
        showInteractive={false}
        className="!bg-card !border-border !rounded-lg !shadow-md [&_button]:!bg-card [&_button]:!border-border [&_button]:!text-muted-foreground [&_button:hover]:!bg-muted"
      />
      <MiniMap
        pannable
        zoomable
        className="!bg-card !border !border-border !rounded-lg"
        maskColor="hsl(var(--background) / 0.65)"
        nodeColor={(n) => {
          const nd = (n.data as unknown as NodeData)?.node;
          const lvl = (nd?.risk as { level?: string } | null)?.level;
          if (lvl === "Critical" || lvl === "High") return "hsl(var(--destructive) / 0.7)";
          if (lvl === "Medium") return "hsl(38 92% 50% / 0.7)";
          return "hsl(var(--muted-foreground) / 0.4)";
        }}
      />
    </ReactFlow>
  );
}

// ---------------------------------------------------------------------------
// Legend primitives
// ---------------------------------------------------------------------------
function LegendDot({ className, label }: { className: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-muted-foreground">
      <span className={cn("w-2 h-2 rounded-full", className)} />
      {label}
    </span>
  );
}

function LegendLine({ className, label, dashed }: { className: string; label: string; dashed?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1 text-muted-foreground">
      <span className={cn("inline-block w-4", dashed ? "h-0" : "h-0.5 rounded", className)} />
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Public canvas
// ---------------------------------------------------------------------------
export function GraphCanvas({
  nodes,
  edges,
  selectedId,
  onSelect,
}: {
  nodes: GraphNodeOut[];
  edges: GraphEdgeOut[];
  selectedId?: number | null;
  onSelect: (nodeId: number) => void;
}) {
  return (
    <div className="h-[680px] w-full rounded-xl border border-border bg-background/40 overflow-hidden">
      <ReactFlowProvider>
        <Flow nodes={nodes} edges={edges} selectedId={selectedId} onSelect={onSelect} />
      </ReactFlowProvider>
    </div>
  );
}
