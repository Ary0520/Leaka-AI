"""
Reconciliation engine — merge a fresh explore run's discoveries into the
persistent Application Graph (Requirements 1.3–1.6, 2.2–2.4, 10.3).

This is a PURE FUNCTION module (input data → output data; no DB, no network, no
randomness), mirroring `fingerprint.py`. The `graph_worker` (Task 6) performs
all the I/O: it loads the current graph into the plain `ExistingNode` /
`ExistingEdge` inputs here, calls `reconcile(...)`, then persists the resulting
`ReconcileResult` inside a single transaction under a Postgres advisory lock.

Keeping the algorithm pure is what makes Properties 1 (idempotency), 3
(append-only snapshots), and 5 (manual-override supremacy) directly
property-testable without a database.

Algorithm (design 1.3):
  1. For each discovery: compute fingerprint, find the best-matching ACTIVE
     node by identity_match_score. score >= MATCH_THRESHOLD → MATCH (update
     last_seen, append a fingerprint version if it drifted); else → NEW node.
  2. Any active node NOT matched this run → mark STALE (never deleted).
  3. Derive edges from whatever relationship evidence the run actually provides
     (navigates_to / contains / part_of_flow / requires_role / depends_on).
     Merge idempotently by (source_key, target_key, edge_type). We NEVER
     fabricate an edge for which there is no evidence (R2.2, R2.3).
  4. Re-apply manual_overrides on matched nodes — overrides always win (R2.7).
  5. Produce a snapshot (frozen member states) + diff_summary vs the previous
     snapshot.
  6. Return a ReconcileResult describing every intended change.

Determinism (R10.3): discoveries are processed in a stable canonical order and
all outputs are sorted by canonical_key / edge dedup key, so identical inputs
always yield identical outputs and re-running is a no-op.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .fingerprint import (
    Discovery,
    Fingerprint,
    NodeSignatures,
    MATCH_THRESHOLD,
    compute_canonical_key,
    compute_fingerprint,
    identity_match_score,
)


# ---------------------------------------------------------------------------
# Plain (ORM-free) representations of existing graph state — the worker maps
# GraphNode/GraphEdge rows onto these before calling reconcile().
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ExistingNode:
    """An active graph node as reconcile() needs to see it."""
    canonical_key: str
    node_type: str
    label: str
    url_pattern: Optional[str] = None
    business_category: Optional[str] = None
    role_association: str = "unknown"
    status: str = "active"                      # active|stale
    signatures: Optional[NodeSignatures] = None  # latest fingerprint signatures
    # Authoritative human edits (win over anything computed). Keys are a subset
    # of {node_type, business_category, role_association, label, risk}.
    manual_overrides: dict = field(default_factory=dict)

    def to_signatures(self) -> NodeSignatures:
        """Fall back to metadata-derived signatures if none were stored."""
        if self.signatures is not None:
            return self.signatures
        # Best-effort: derive from the node's own metadata so a freshly
        # backfilled node (no stored fingerprint yet) can still be matched.
        from .fingerprint import normalize_url, _sha16, _normalize_text  # local, pure
        return NodeSignatures(
            node_type=self.node_type,
            url_signature=normalize_url(self.url_pattern),
            text_signature=_sha16(_normalize_text(self.label)),
        )


@dataclass(frozen=True)
class ExistingEdge:
    """An active graph edge, identified by its deterministic dedup key."""
    source_key: str
    target_key: str
    edge_type: str
    confidence: int = 100
    status: str = "active"


@dataclass(frozen=True)
class EdgeEvidence:
    """
    A single piece of relationship evidence a run may provide. The engine only
    ever emits edges backed by one of these — never inferred out of thin air.

    `source`/`target` are canonical keys (the worker computes them the same way
    reconcile() does, or leaves edge_evidence empty when the explorer captured
    no relationships — which is the case for the current flat explorer).
    """
    source_key: str
    target_key: str
    edge_type: str            # navigates_to|contains|requires_role|depends_on|part_of_flow
    confidence: int = 100


# ---------------------------------------------------------------------------
# Result records — everything reconcile() decided (the worker applies them).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class NodeChange:
    canonical_key: str
    node_type: str
    label: str
    url_pattern: Optional[str]
    business_category: Optional[str]
    role_association: str
    fingerprint: Fingerprint
    change: str                       # "new" | "matched" | "staled"
    fingerprint_drifted: bool = False  # matched nodes only: signatures changed


@dataclass(frozen=True)
class EdgeChange:
    source_key: str
    target_key: str
    edge_type: str
    confidence: int
    change: str                       # "new" | "matched" | "staled"


@dataclass(frozen=True)
class SnapshotMemberState:
    """Frozen state of one node at snapshot time (basis for diffing)."""
    canonical_key: str
    node_type: str
    label: str
    url_pattern: Optional[str]
    business_category: Optional[str]
    role_association: str
    status: str
    text_signature: str
    url_signature: str


@dataclass(frozen=True)
class ReconcileResult:
    nodes: list[NodeChange]
    edges: list[EdgeChange]
    members: list[SnapshotMemberState]   # the new snapshot's frozen members
    diff_summary: dict                   # vs previous snapshot
    node_count: int
    edge_count: int

    @property
    def added_nodes(self) -> list[NodeChange]:
        return [n for n in self.nodes if n.change == "new"]

    @property
    def staled_nodes(self) -> list[NodeChange]:
        return [n for n in self.nodes if n.change == "staled"]


# ---------------------------------------------------------------------------
# Manual-override application (overrides always win — Property 5)
# ---------------------------------------------------------------------------
_OVERRIDABLE_FIELDS = ("node_type", "business_category", "role_association", "label")


def _apply_overrides(
    *,
    node_type: str,
    label: str,
    url_pattern: Optional[str],
    business_category: Optional[str],
    role_association: str,
    overrides: dict,
) -> tuple[str, str, Optional[str], Optional[str], str]:
    """Overlay authoritative human edits last so they survive reconciliation."""
    if overrides:
        if "node_type" in overrides and overrides["node_type"]:
            node_type = str(overrides["node_type"]).strip().lower()
        if "label" in overrides and overrides["label"] is not None:
            label = str(overrides["label"])
        if "business_category" in overrides:
            business_category = overrides["business_category"]
        if "role_association" in overrides and overrides["role_association"]:
            role_association = str(overrides["role_association"])
    return node_type, label, url_pattern, business_category, role_association


# ---------------------------------------------------------------------------
# The pure reconciliation function
# ---------------------------------------------------------------------------
def reconcile(
    existing_nodes: list[ExistingNode],
    existing_edges: list[ExistingEdge],
    discoveries: list[Discovery],
    *,
    edge_evidence: Optional[list[EdgeEvidence]] = None,
    previous_members: Optional[list[SnapshotMemberState]] = None,
) -> ReconcileResult:
    """
    Merge `discoveries` into the existing graph. Pure and deterministic.

    Args:
      existing_nodes:   the current ACTIVE + stale graph nodes (plain form).
      existing_edges:   the current graph edges (plain form).
      discoveries:      this run's raw discoveries (fingerprint.Discovery).
      edge_evidence:    optional relationship evidence; only these produce edges.
      previous_members: the previous snapshot's frozen members (for diffing).

    Returns a ReconcileResult the caller persists inside one transaction.
    """
    edge_evidence = edge_evidence or []
    previous_members = previous_members or []

    # Index existing ACTIVE nodes by canonical_key for O(1) match/lookup, and
    # keep a stable, canonical-key-sorted list for deterministic iteration.
    active_by_key: dict[str, ExistingNode] = {
        n.canonical_key: n for n in existing_nodes if n.status == "active"
    }
    all_by_key: dict[str, ExistingNode] = {n.canonical_key: n for n in existing_nodes}

    matched_keys: set[str] = set()
    node_changes: dict[str, NodeChange] = {}

    # Deduplicate discoveries by canonical_key first (two discoveries that map
    # to the same identity collapse to one node — this is what makes overlapping
    # discoveries idempotent, R1.6). Process in stable canonical-key order.
    disc_by_key: dict[str, Discovery] = {}
    for d in discoveries:
        key = compute_canonical_key(d)
        # First writer wins for a given key within a run (stable + deterministic
        # because we then iterate keys sorted); later duplicates are the same
        # identity so their metadata is redundant.
        disc_by_key.setdefault(key, d)

    for key in sorted(disc_by_key.keys()):
        discovery = disc_by_key[key]
        fp = compute_fingerprint(discovery)
        node_type = (discovery.node_type or "page").strip().lower()

        # ── Find the best-matching ACTIVE node by identity score ──────────
        best_key: Optional[str] = None
        best_score = 0.0
        for cand_key in sorted(active_by_key.keys()):
            cand = active_by_key[cand_key]
            s = identity_match_score(discovery, cand.to_signatures())
            # Deterministic tie-break: strictly greater wins; equal scores keep
            # the lexicographically-smaller canonical_key already chosen.
            if s > best_score:
                best_score = s
                best_key = cand_key

        if best_key is not None and best_score >= MATCH_THRESHOLD:
            # ── MATCH ──────────────────────────────────────────────────────
            existing = active_by_key[best_key]
            matched_keys.add(best_key)

            prior = existing.to_signatures()
            drifted = (
                prior.url_signature != fp.url_signature
                or prior.text_signature != fp.text_signature
                or (prior.dom_signature or None) != (fp.dom_signature or None)
                or (prior.aria_signature or None) != (fp.aria_signature or None)
            )

            # New computed metadata from the discovery, then overrides win.
            nt, lbl, urlp, bcat, role = _apply_overrides(
                node_type=node_type,
                label=(discovery.label or existing.label),
                url_pattern=(fp.url_signature or existing.url_pattern),
                business_category=existing.business_category,
                role_association=existing.role_association,
                overrides=existing.manual_overrides,
            )
            node_changes[best_key] = NodeChange(
                canonical_key=best_key,
                node_type=nt,
                label=lbl,
                url_pattern=urlp,
                business_category=bcat,
                role_association=role,
                fingerprint=fp,
                change="matched",
                fingerprint_drifted=drifted,
            )
        else:
            # ── NEW ───────────────────────────────────────────────────────
            nt, lbl, urlp, bcat, role = _apply_overrides(
                node_type=node_type,
                label=(discovery.label or ""),
                url_pattern=(fp.url_signature or None),
                business_category=None,
                role_association="unknown",
                overrides={},  # brand-new node has no overrides yet
            )
            node_changes[key] = NodeChange(
                canonical_key=key,
                node_type=nt,
                label=lbl,
                url_pattern=urlp,
                business_category=bcat,
                role_association=role,
                fingerprint=fp,
                change="new",
                fingerprint_drifted=False,
            )

    # ── Step 2: active nodes not matched this run → STALE (never deleted) ──
    for key in sorted(active_by_key.keys()):
        if key in matched_keys:
            continue
        n = active_by_key[key]
        sig = n.to_signatures()
        node_changes[key] = NodeChange(
            canonical_key=key,
            node_type=n.node_type,
            label=n.label,
            url_pattern=n.url_pattern,
            business_category=n.business_category,
            role_association=n.role_association,
            fingerprint=Fingerprint(
                url_signature=sig.url_signature,
                text_signature=sig.text_signature,
                dom_signature=sig.dom_signature,
                aria_signature=sig.aria_signature,
            ),
            change="staled",
            fingerprint_drifted=False,
        )

    # ── Step 3: derive edges from evidence only, dedup by (src,tgt,type) ───
    edge_changes = _reconcile_edges(existing_edges, edge_evidence)

    # ── Step 5: build snapshot members (all non-removed nodes' frozen state)
    members = _build_members(node_changes)
    active_members = [m for m in members if m.status == "active"]
    active_edges = [e for e in edge_changes if e.change != "staled"]

    diff_summary = _diff_members(previous_members, members, edge_changes)

    return ReconcileResult(
        nodes=sorted(node_changes.values(), key=lambda c: c.canonical_key),
        edges=edge_changes,
        members=members,
        diff_summary=diff_summary,
        node_count=len(active_members),
        edge_count=len(active_edges),
    )


# ---------------------------------------------------------------------------
# Edge reconciliation (deterministic dedup by (source, target, edge_type))
# ---------------------------------------------------------------------------
def _edge_key(source_key: str, target_key: str, edge_type: str) -> tuple[str, str, str]:
    return (source_key, target_key, (edge_type or "").strip().lower())


def _reconcile_edges(
    existing_edges: list[ExistingEdge],
    evidence: list[EdgeEvidence],
) -> list[EdgeChange]:
    existing_active: dict[tuple[str, str, str], ExistingEdge] = {
        _edge_key(e.source_key, e.target_key, e.edge_type): e
        for e in existing_edges
        if e.status == "active"
    }
    seen: dict[tuple[str, str, str], EdgeChange] = {}

    # Every evidenced edge is either a match (already exists) or new.
    for ev in evidence:
        k = _edge_key(ev.source_key, ev.target_key, ev.edge_type)
        if k in seen:
            continue  # idempotent within a run
        change = "matched" if k in existing_active else "new"
        seen[k] = EdgeChange(
            source_key=k[0],
            target_key=k[1],
            edge_type=k[2],
            confidence=int(ev.confidence),
            change=change,
        )

    # Existing edges not re-evidenced this run → staled (never deleted).
    for k, e in existing_active.items():
        if k not in seen:
            seen[k] = EdgeChange(
                source_key=k[0],
                target_key=k[1],
                edge_type=k[2],
                confidence=int(e.confidence),
                change="staled",
            )

    return sorted(seen.values(), key=lambda e: (e.source_key, e.target_key, e.edge_type))


# ---------------------------------------------------------------------------
# Snapshot members + diffing
# ---------------------------------------------------------------------------
def _build_members(node_changes: dict[str, NodeChange]) -> list[SnapshotMemberState]:
    members: list[SnapshotMemberState] = []
    for key in sorted(node_changes.keys()):
        c = node_changes[key]
        status = "stale" if c.change == "staled" else "active"
        members.append(
            SnapshotMemberState(
                canonical_key=c.canonical_key,
                node_type=c.node_type,
                label=c.label,
                url_pattern=c.url_pattern,
                business_category=c.business_category,
                role_association=c.role_association,
                status=status,
                text_signature=c.fingerprint.text_signature,
                url_signature=c.fingerprint.url_signature,
            )
        )
    return members


def _member_metadata_tuple(m: SnapshotMemberState) -> tuple:
    """The fields whose change means a node 'changed' between snapshots."""
    return (
        m.node_type,
        m.label,
        m.url_pattern,
        m.business_category,
        m.role_association,
        m.status,
        m.text_signature,
        m.url_signature,
    )


def _diff_members(
    prev: list[SnapshotMemberState],
    curr: list[SnapshotMemberState],
    edges: list[EdgeChange],
) -> dict:
    """
    Compare two snapshots' frozen members by canonical_key (design 1.4).

    added   : keys in curr not in prev
    removed : keys in prev not in curr (staled/removed)
    changed : same key, different metadata/fingerprint
    Edge deltas are derived from this run's edge changes.
    """
    prev_by_key = {m.canonical_key: m for m in prev}
    curr_by_key = {m.canonical_key: m for m in curr}

    added = sorted(k for k in curr_by_key if k not in prev_by_key)
    removed = sorted(k for k in prev_by_key if k not in curr_by_key)
    changed = sorted(
        k
        for k in curr_by_key
        if k in prev_by_key
        and _member_metadata_tuple(curr_by_key[k]) != _member_metadata_tuple(prev_by_key[k])
    )

    edges_added = sorted(
        (e.source_key, e.target_key, e.edge_type) for e in edges if e.change == "new"
    )
    edges_staled = sorted(
        (e.source_key, e.target_key, e.edge_type) for e in edges if e.change == "staled"
    )

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "edges_added": [list(t) for t in edges_added],
        "edges_removed": [list(t) for t in edges_staled],
        "counts": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "edges_added": len(edges_added),
            "edges_removed": len(edges_staled),
        },
    }


# ---------------------------------------------------------------------------
# Public snapshot diff (R1.5, R8.3) — compare any two stored snapshots
# ---------------------------------------------------------------------------
def diff_snapshots(
    a_members: list[SnapshotMemberState],
    b_members: list[SnapshotMemberState],
) -> dict:
    """
    Diff snapshot A (older) vs snapshot B (newer): added/removed/changed nodes.
    Edge deltas are not part of a members-only comparison, so they are empty
    here; the reconcile() diff_summary carries edge deltas for the run diff.
    """
    return _diff_members(a_members, b_members, edges=[])
