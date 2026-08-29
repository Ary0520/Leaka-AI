"""
Diff → affected-flow mapping engine (Requirements 7.1–7.8; design Layer 4.3).

PURE FUNCTION module (input data → output data; no I/O, no randomness), like
`risk.py` and `coverage.py`. The repo_worker (Task 20) loads the ORM state into
the plain inputs here, calls `map_diff(...)`, and persists the FlowMappings.

Given a code diff + the application graph + coverage state, it produces a ranked
list of affected graph nodes, each with:
  - the explainable signals that fired (route / component / semantic),
  - a confidence,
  - the recommended test_case ids (via coverage links), ranked by node risk,
  - the coverage state (covered | uncovered | undetermined),
  - the explain chain (changed file → node → covering test).

Signals (design 4.3, R7.2):
  1. Route/path correspondence — changed file path tokens matched to a node's
     normalized url_pattern.
  2. Component→page association — caller-supplied hints (learned from memory or
     the graph: which components render which nodes).
  3. Semantic similarity — a PRECOMPUTED cosine per (file, node) supplied by the
     caller (the embedding I/O lives in the worker, keeping this engine pure —
     the same boundary used by the coverage engine).

Empty vs stale graph (R7.7, Property 10):
  - EMPTY graph → an explicit "no recommendations — explore first" result with an
    EMPTY mapping list. We NEVER fabricate a recommendation for an unexplored app.
  - STALE graph → a conservative recommendation (all high-risk nodes' tests),
    labeled low-confidence, suggesting a re-explore.

Determinism (R7.8, Property 9): pure function of (diff, graph, coverage). All
outputs are sorted by (risk desc, canonical_key asc); ties never depend on input
order or randomness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .fingerprint import normalize_url


# Graph states.
GRAPH_EMPTY = "empty"
GRAPH_ACTIVE = "active"
GRAPH_STALE = "stale"

# Coverage states (mirror the coverage engine).
COV_COVERED = "covered"
COV_UNCOVERED = "uncovered"
COV_UNDETERMINED = "undetermined"

# Signal thresholds.
_SEMANTIC_MATCH_THRESHOLD = 0.72
_HIGH_RISK_SCORE = 60  # nodes at/above this are "high-risk" for stale fallback


# ---------------------------------------------------------------------------
# Plain inputs
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ChangedFile:
    path: str
    status: str = "modified"                # added|modified|removed|renamed


@dataclass(frozen=True)
class MapNode:
    """A graph node as the mapper needs it (plain form; worker maps from ORM)."""
    node_id: int
    canonical_key: str
    url_pattern: Optional[str] = None
    business_category: Optional[str] = None
    risk_score: int = 0
    risk_level: str = "Trivial"
    # Coverage: state + the test_case ids that cover this node (from links).
    coverage_state: str = COV_UNDETERMINED
    covering_test_ids: tuple = ()
    # Suggested prompt (for the "no coverage → generate test" hint).
    suggested_prompt: Optional[str] = None
    # Component→page association hints: file-path substrings that map to this
    # node (learned from memory/graph). Matched against changed file paths.
    component_hints: tuple = ()


@dataclass(frozen=True)
class DiffInput:
    changed_files: tuple                     # tuple[ChangedFile, ...]
    graph_state: str = GRAPH_ACTIVE          # empty|active|stale
    # Precomputed semantic similarity per (file_path, canonical_key) in [0,1].
    semantic: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Result records
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MappingSignal:
    name: str                                # route | component | semantic | stale_fallback
    detail: dict


@dataclass(frozen=True)
class FlowMappingResult:
    node_id: int
    canonical_key: str
    confidence: float                        # [0.0, 1.0]
    signals: tuple                           # tuple[MappingSignal, ...]
    recommended_test_ids: tuple              # ranked test_case ids
    coverage_state: str                      # covered|uncovered|undetermined
    risk_score: int
    risk_level: str
    # Explain chain: changed file → node → covering test (R7.6).
    chain: dict
    no_coverage_warning: bool = False
    suggested_prompt: Optional[str] = None


@dataclass(frozen=True)
class MapResult:
    status: str                              # ok | no_graph | stale
    message: str
    mappings: tuple                          # tuple[FlowMappingResult, ...]
    # Flat, deduped, risk-ranked recommended test ids (CI-consumable, R7.5).
    recommended_test_ids: tuple = ()


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


# ---------------------------------------------------------------------------
# Route correspondence: derive route-ish tokens from a changed file path and
# match them to a node's normalized url_pattern.
# ---------------------------------------------------------------------------
_CODE_EXTS = re.compile(r"\.(tsx?|jsx?|py|rb|go|java|php|vue|svelte|html?)$", re.I)
_IGNORE_SEGMENTS = {
    "src", "app", "pages", "routes", "components", "views", "public", "static",
    "lib", "server", "client", "api", "index", "main", "__init__", "test", "tests",
    "spec", "dist", "build", "node_modules",
}


def _path_tokens(path: str) -> set[str]:
    """
    Extract lowercased, meaningful tokens from a file path for route matching.
    e.g. 'src/pages/Checkout.tsx' → {'checkout'};
         'app/routes/orders/[id].tsx' → {'orders', 'id'}.
    """
    if not path:
        return set()
    p = _CODE_EXTS.sub("", path.strip().lower())
    raw = re.split(r"[\\/._\-\[\]]+", p)
    toks = {t for t in raw if t and t not in _IGNORE_SEGMENTS and not t.isdigit()}
    return toks


def _url_tokens(url_pattern: Optional[str]) -> set[str]:
    """Tokens from a normalized url_pattern, e.g. '/orders/:id' → {'orders'}."""
    norm = normalize_url(url_pattern) if url_pattern else ""
    raw = re.split(r"[\\/:]+", norm.lower())
    return {t for t in raw if t and t != "id" and not t.isdigit()}


def _route_overlap(file_path: str, node: MapNode) -> set[str]:
    """The set of tokens shared between a changed file and a node's route."""
    return _path_tokens(file_path) & _url_tokens(node.url_pattern)


def _component_overlap(file_path: str, node: MapNode) -> list[str]:
    """Component→page hints that appear in the changed file path."""
    fp = (file_path or "").lower()
    return sorted({h for h in node.component_hints if h and h.lower() in fp})


# ---------------------------------------------------------------------------
# The pure mapping function
# ---------------------------------------------------------------------------
def map_diff(diff: DiffInput, nodes: list[MapNode]) -> MapResult:
    """
    Map a diff to affected graph nodes + recommended tests. Pure & deterministic.
    """
    # ── Empty graph: NEVER fabricate (R7.7, Property 10) ───────────────────
    if diff.graph_state == GRAPH_EMPTY or not nodes:
        return MapResult(
            status="no_graph",
            message="No recommendations available — explore this application first.",
            mappings=(),
            recommended_test_ids=(),
        )

    # ── Stale graph: conservative fallback (R7.7) ──────────────────────────
    if diff.graph_state == GRAPH_STALE:
        return _stale_fallback(nodes)

    # ── Active graph: signal-based mapping ─────────────────────────────────
    mappings: list[FlowMappingResult] = []
    for node in nodes:
        signals: list[MappingSignal] = []
        matched_files: list[str] = []
        confidence = 0.0

        for f in diff.changed_files:
            route_tokens = _route_overlap(f.path, node)
            if route_tokens:
                signals.append(MappingSignal(
                    name="route",
                    detail={"file": f.path, "matched_tokens": sorted(route_tokens)},
                ))
                matched_files.append(f.path)
                confidence = max(confidence, 0.80)

            comp = _component_overlap(f.path, node)
            if comp:
                signals.append(MappingSignal(
                    name="component",
                    detail={"file": f.path, "matched_hints": comp},
                ))
                matched_files.append(f.path)
                confidence = max(confidence, 0.70)

            sim = diff.semantic.get((f.path, node.canonical_key))
            if sim is not None and sim >= _SEMANTIC_MATCH_THRESHOLD:
                signals.append(MappingSignal(
                    name="semantic",
                    detail={"file": f.path, "similarity": round(float(sim), 4)},
                ))
                matched_files.append(f.path)
                # Semantic contributes proportionally, capped below exact-route.
                confidence = max(confidence, _clamp01(0.40 + 0.35 * (sim - _SEMANTIC_MATCH_THRESHOLD)
                                                       / max(1e-9, 1.0 - _SEMANTIC_MATCH_THRESHOLD)))

        if not signals:
            continue  # this node is not affected by the diff

        # Recommended tests: the node's covering tests (R7.3), deduped + stable.
        rec_tests = tuple(sorted(set(node.covering_test_ids)))

        # No-coverage warning (R7.4).
        no_cov = len(rec_tests) == 0
        warn = False
        if no_cov:
            if node.coverage_state == COV_UNDETERMINED:
                warn = True  # surfaced, but labeled undetermined via coverage_state
            else:
                warn = True  # high-confidence: coverage computed & uncovered

        mappings.append(FlowMappingResult(
            node_id=node.node_id,
            canonical_key=node.canonical_key,
            confidence=round(_clamp01(confidence), 6),
            signals=tuple(signals),
            recommended_test_ids=rec_tests,
            coverage_state=node.coverage_state,
            risk_score=node.risk_score,
            risk_level=node.risk_level,
            chain={
                "changed_files": sorted(set(matched_files)),
                "node": node.canonical_key,
                "covering_tests": list(rec_tests),
            },
            no_coverage_warning=no_cov and warn,
            suggested_prompt=node.suggested_prompt if no_cov else None,
        ))

    # Rank by risk desc, then canonical_key asc (deterministic — Property 9).
    mappings.sort(key=lambda m: (-m.risk_score, m.canonical_key))

    # Flat CI-consumable recommended test ids, ranked by the node ordering.
    flat: list[int] = []
    seen: set[int] = set()
    for m in mappings:
        for tid in m.recommended_test_ids:
            if tid not in seen:
                seen.add(tid)
                flat.append(tid)

    return MapResult(
        status="ok",
        message=f"{len(mappings)} affected flow(s) mapped.",
        mappings=tuple(mappings),
        recommended_test_ids=tuple(flat),
    )


def _stale_fallback(nodes: list[MapNode]) -> MapResult:
    """
    Conservative recommendation for a stale graph (R7.7): recommend all
    high-risk nodes' tests, low-confidence, suggest re-exploring. Deterministic.
    """
    mappings: list[FlowMappingResult] = []
    for node in nodes:
        if node.risk_score < _HIGH_RISK_SCORE:
            continue
        rec_tests = tuple(sorted(set(node.covering_test_ids)))
        mappings.append(FlowMappingResult(
            node_id=node.node_id,
            canonical_key=node.canonical_key,
            confidence=0.30,  # low-confidence, explicitly
            signals=(MappingSignal(
                name="stale_fallback",
                detail={"reason": "graph is stale; recommending high-risk flows conservatively"},
            ),),
            recommended_test_ids=rec_tests,
            coverage_state=node.coverage_state,
            risk_score=node.risk_score,
            risk_level=node.risk_level,
            chain={"changed_files": [], "node": node.canonical_key,
                   "covering_tests": list(rec_tests)},
            no_coverage_warning=(len(rec_tests) == 0),
            suggested_prompt=node.suggested_prompt if not rec_tests else None,
        ))
    mappings.sort(key=lambda m: (-m.risk_score, m.canonical_key))

    flat: list[int] = []
    seen: set[int] = set()
    for m in mappings:
        for tid in m.recommended_test_ids:
            if tid not in seen:
                seen.add(tid)
                flat.append(tid)

    return MapResult(
        status="stale",
        message="Graph may be out of date — recommending high-risk flows conservatively. "
                "Re-explore this application for precise recommendations.",
        mappings=tuple(mappings),
        recommended_test_ids=tuple(flat),
    )


# ---------------------------------------------------------------------------
# Serialization helper (persist into FlowMapping rows / API responses)
# ---------------------------------------------------------------------------
def mapping_to_dict(m: FlowMappingResult) -> dict:
    return {
        "node_id": m.node_id,
        "canonical_key": m.canonical_key,
        "confidence": m.confidence,
        "signals": [{"name": s.name, "detail": s.detail} for s in m.signals],
        "recommended_test_ids": list(m.recommended_test_ids),
        "coverage_state": m.coverage_state,
        "risk_score": m.risk_score,
        "risk_level": m.risk_level,
        "chain": m.chain,
        "no_coverage_warning": m.no_coverage_warning,
        "suggested_prompt": m.suggested_prompt,
    }


def confidence_to_milli(confidence: float) -> int:
    """[0,1] → integer 0..1000 for the FlowMapping.confidence_milli column."""
    return int(round(_clamp01(confidence) * 1000))
