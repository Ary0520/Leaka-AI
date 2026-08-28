"""
Coverage engine — multi-signal, explainable coverage classification
(Requirements 4.1–4.9; design Layer 2.2).

Supersedes the substring heuristic currently inline in
`GET /api/applications/{id}/map`. For each graph node it classifies coverage as
`covered | partially_covered | uncovered` with a confidence in [0.0, 1.0] and an
evidence list describing exactly which signals contributed (R4.1, R4.8).

PURITY BOUNDARY (why this module does no I/O):
  The semantic-similarity signal (R4.2c) requires an embedder + vector search,
  which is I/O. To keep this engine pure and directly property-testable
  (Properties 6 & 7), the CALLER (coverage worker, Task 12) performs the
  embedding/pgvector query and passes the resulting cosine similarity in as a
  precomputed number on each CoverageTest. The engine only combines signals.
  This matches the "pure engines, thin workers" principle used across
  fingerprint.py / reconciliation.py / risk.py.

Signals, strongest first (design 2.2):
  1. Explicit link (authoritative, R4.3)      — a coverage_links row exists.
  2. Route correspondence (R4.2b)             — test.target_url normalizes to
                                                 the node's url_pattern.
  3. Semantic similarity (R4.2c)              — precomputed cosine ∈ [0,1].

Recent pass/fail (R4.7) modulates CONFIDENCE (not existence): a linked,
recently-passing test yields higher confidence than one whose only test is
failing. "Test exists" and "test exists and passes" are distinct inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .fingerprint import normalize_url


# ---------------------------------------------------------------------------
# States (ordered weakest → strongest for monotonicity reasoning)
# ---------------------------------------------------------------------------
UNCOVERED = "uncovered"
PARTIALLY_COVERED = "partially_covered"
COVERED = "covered"

_STATE_RANK = {UNCOVERED: 0, PARTIALLY_COVERED: 1, COVERED: 2}

# Route/semantic thresholds.
_SEMANTIC_PARTIAL_THRESHOLD = 0.72   # >= contributes partial coverage
_SEMANTIC_STRONG_THRESHOLD = 0.88    # >= is a strong (near-explicit) signal


# ---------------------------------------------------------------------------
# Plain (ORM-free) inputs
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CoverageTest:
    """One test case's relationship signals to a node (precomputed by caller)."""
    test_case_id: int
    target_url: Optional[str] = None
    name: Optional[str] = None
    prompt: Optional[str] = None
    # Signal 1: an authoritative coverage_link exists between this test & node.
    linked: bool = False
    link_source: Optional[str] = None            # generated|manual (when linked)
    # Signal 3: precomputed cosine similarity in [0,1], or None if unavailable
    # (embedder down / not computed → semantic signal simply skipped, R10.4).
    semantic_similarity: Optional[float] = None
    # Recent outcome for this test: True passed, False failed, None unknown.
    last_run_passed: Optional[bool] = None


@dataclass(frozen=True)
class CoverageNode:
    node_id: int
    canonical_key: str
    url_pattern: Optional[str] = None
    business_category: Optional[str] = None
    status: str = "active"                        # active|stale
    # Risk for rollup weighting (from risk engine); score in 0..100.
    risk_score: int = 0
    risk_level: str = "Trivial"


@dataclass(frozen=True)
class CoverageEvidence:
    signal: str                                   # explicit_link|route|semantic
    detail: dict


@dataclass(frozen=True)
class CoverageVerdict:
    node_id: int
    state: str
    confidence: float                             # [0.0, 1.0]
    evidence: tuple                               # tuple[CoverageEvidence, ...]
    linked_test_ids: tuple = ()


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _route_matches(test_url: Optional[str], node_pattern: Optional[str]) -> bool:
    """
    Route correspondence: the test's target_url, normalized the SAME way node
    url_patterns are (fingerprint.normalize_url), equals the node's url_pattern.
    """
    if not test_url or not node_pattern:
        return False
    return normalize_url(test_url) == node_pattern


# ---------------------------------------------------------------------------
# Per-node classification
# ---------------------------------------------------------------------------
def classify_node_coverage(
    node: CoverageNode,
    tests: list[CoverageTest],
) -> CoverageVerdict:
    """
    Classify a single node's coverage from its candidate tests. Pure &
    deterministic. Confidence always in [0.0, 1.0] (Property 7). Adding an
    authoritative link never lowers the state; removing all tests → uncovered
    (Property 6).
    """
    evidence: list[CoverageEvidence] = []
    linked_test_ids: list[int] = []

    best_state = UNCOVERED
    best_confidence = 0.0

    # Track the strongest passing/failing status among contributing tests to
    # modulate confidence (R4.7).
    any_linked = False
    any_linked_passing = False
    any_linked_failing = False

    for t in tests:
        # ── Signal 1: explicit authoritative link (strongest) ─────────────
        if t.linked:
            any_linked = True
            linked_test_ids.append(t.test_case_id)
            # A linked test means the flow IS tested → state is COVERED even if
            # the test is currently failing; only CONFIDENCE drops in that case
            # ("test exists" vs "test exists and passes" are distinct — R4.7).
            state = COVERED
            # confidence: passing 0.95, unknown 0.85, failing 0.55
            if t.last_run_passed is True:
                conf = 0.95
                any_linked_passing = True
            elif t.last_run_passed is False:
                conf = 0.55
                any_linked_failing = True
            else:
                conf = 0.85
            evidence.append(CoverageEvidence(
                signal="explicit_link",
                detail={"test_case_id": t.test_case_id, "source": t.link_source,
                        "last_run_passed": t.last_run_passed},
            ))
            if _STATE_RANK[state] > _STATE_RANK[best_state] or (
                _STATE_RANK[state] == _STATE_RANK[best_state] and conf > best_confidence
            ):
                best_state, best_confidence = state, conf
            continue

        # ── Signal 2: route correspondence ────────────────────────────────
        if _route_matches(t.target_url, node.url_pattern):
            state = COVERED
            conf = 0.80 if t.last_run_passed is not False else 0.50
            if t.last_run_passed is True:
                conf = 0.88
            evidence.append(CoverageEvidence(
                signal="route",
                detail={"test_case_id": t.test_case_id,
                        "target_url": t.target_url, "url_pattern": node.url_pattern,
                        "last_run_passed": t.last_run_passed},
            ))
            if _STATE_RANK[state] > _STATE_RANK[best_state] or (
                _STATE_RANK[state] == _STATE_RANK[best_state] and conf > best_confidence
            ):
                best_state, best_confidence = state, conf
            continue

        # ── Signal 3: semantic similarity (precomputed cosine) ────────────
        sim = t.semantic_similarity
        if sim is not None and sim >= _SEMANTIC_PARTIAL_THRESHOLD:
            if sim >= _SEMANTIC_STRONG_THRESHOLD:
                state = COVERED
                conf = _clamp01(0.60 + 0.30 * (sim - _SEMANTIC_STRONG_THRESHOLD)
                                / max(1e-9, 1.0 - _SEMANTIC_STRONG_THRESHOLD))
            else:
                state = PARTIALLY_COVERED
                conf = _clamp01(0.35 + 0.30 * (sim - _SEMANTIC_PARTIAL_THRESHOLD)
                                / max(1e-9, _SEMANTIC_STRONG_THRESHOLD - _SEMANTIC_PARTIAL_THRESHOLD))
            if t.last_run_passed is False:
                conf *= 0.7  # a failing semantically-similar test is weaker
            evidence.append(CoverageEvidence(
                signal="semantic",
                detail={"test_case_id": t.test_case_id, "similarity": round(sim, 4),
                        "last_run_passed": t.last_run_passed},
            ))
            if _STATE_RANK[state] > _STATE_RANK[best_state] or (
                _STATE_RANK[state] == _STATE_RANK[best_state] and conf > best_confidence
            ):
                best_state, best_confidence = state, conf

    # ── Monotonicity guard (Property 6): a link must NEVER yield uncovered.
    if any_linked and _STATE_RANK[best_state] < _STATE_RANK[PARTIALLY_COVERED]:
        best_state = PARTIALLY_COVERED
        best_confidence = max(best_confidence, 0.55)

    # Downgrade note: if the ONLY signals are linked-but-all-failing, keep
    # covered state (flow is tested) with the lower confidence already set.
    _ = (any_linked_passing, any_linked_failing)  # retained for clarity/evidence

    return CoverageVerdict(
        node_id=node.node_id,
        state=best_state,
        confidence=round(_clamp01(best_confidence), 6),
        evidence=tuple(evidence),
        linked_test_ids=tuple(sorted(set(linked_test_ids))),
    )


# ---------------------------------------------------------------------------
# Risk-weighted rollups (R4.4)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CoverageRollup:
    scope: str                                    # "application" | category name
    covered_weight: float
    total_weight: float
    percent: float                                # risk-weighted coverage %
    node_count: int
    covered_count: int
    partial_count: int
    uncovered_count: int


def _state_weight_factor(state: str) -> float:
    """Covered counts fully, partial half, uncovered zero — for rollups."""
    return {COVERED: 1.0, PARTIALLY_COVERED: 0.5, UNCOVERED: 0.0}[state]


def _risk_weight(node: CoverageNode) -> float:
    """
    Risk weight for rollups: a covered Trivial node and an uncovered Critical
    node are not equal (R4.4). Weight is (risk_score + 1) so even trivial nodes
    carry a small nonzero weight and never divide-by-zero.
    """
    return float(node.risk_score) + 1.0


def rollup(
    verdicts_by_node: dict[int, CoverageVerdict],
    nodes: list[CoverageNode],
) -> dict[str, CoverageRollup]:
    """
    Compute the application rollup and per-business_category rollups, all
    risk-weighted. Only ACTIVE nodes are counted. Deterministic.
    """
    scopes: dict[str, dict] = {}

    def _acc(scope: str, node: CoverageNode, verdict: CoverageVerdict):
        s = scopes.setdefault(scope, {
            "covered_weight": 0.0, "total_weight": 0.0,
            "node_count": 0, "covered_count": 0, "partial_count": 0, "uncovered_count": 0,
        })
        w = _risk_weight(node)
        s["total_weight"] += w
        s["covered_weight"] += w * _state_weight_factor(verdict.state)
        s["node_count"] += 1
        if verdict.state == COVERED:
            s["covered_count"] += 1
        elif verdict.state == PARTIALLY_COVERED:
            s["partial_count"] += 1
        else:
            s["uncovered_count"] += 1

    for node in nodes:
        if node.status != "active":
            continue
        verdict = verdicts_by_node.get(
            node.node_id,
            CoverageVerdict(node_id=node.node_id, state=UNCOVERED, confidence=0.0, evidence=()),
        )
        _acc("application", node, verdict)
        cat = (node.business_category or "unknown").strip().lower()
        _acc(cat, node, verdict)

    out: dict[str, CoverageRollup] = {}
    for scope, s in scopes.items():
        total_w = s["total_weight"]
        pct = (s["covered_weight"] / total_w * 100.0) if total_w > 0 else 0.0
        out[scope] = CoverageRollup(
            scope=scope,
            covered_weight=round(s["covered_weight"], 4),
            total_weight=round(total_w, 4),
            percent=round(pct, 2),
            node_count=s["node_count"],
            covered_count=s["covered_count"],
            partial_count=s["partial_count"],
            uncovered_count=s["uncovered_count"],
        )
    return out


# ---------------------------------------------------------------------------
# Prioritized coverage gaps (R4.5)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CoverageGap:
    node_id: int
    canonical_key: str
    state: str
    confidence: float
    risk_score: int
    risk_level: str
    business_category: Optional[str]


def gaps(
    verdicts_by_node: dict[int, CoverageVerdict],
    nodes: list[CoverageNode],
) -> list[CoverageGap]:
    """
    Uncovered / partially-covered ACTIVE nodes, ranked by risk descending; ties
    broken by canonical_key ascending (deterministic). Each gap carries the info
    the UI needs to offer one-click test generation (R4.5); the suggested_prompt
    itself lives on the AppMapNode and is joined by the caller.
    """
    result: list[CoverageGap] = []
    for node in nodes:
        if node.status != "active":
            continue
        v = verdicts_by_node.get(node.node_id)
        state = v.state if v else UNCOVERED
        if state == COVERED:
            continue
        result.append(CoverageGap(
            node_id=node.node_id,
            canonical_key=node.canonical_key,
            state=state,
            confidence=v.confidence if v else 0.0,
            risk_score=node.risk_score,
            risk_level=node.risk_level,
            business_category=node.business_category,
        ))
    return sorted(result, key=lambda g: (-g.risk_score, g.canonical_key))


# ---------------------------------------------------------------------------
# Orphan detection (R4.9)
# ---------------------------------------------------------------------------
def detect_orphans(
    links: list[tuple[int, int]],
    stale_node_ids: set[int],
) -> list[tuple[int, int]]:
    """
    Given (link_id, node_id) pairs and the set of stale node ids, return the
    links whose node has gone stale — to be FLAGGED orphaned, not dropped
    (R4.9). Deterministic order.
    """
    return sorted([(lid, nid) for (lid, nid) in links if nid in stale_node_ids])


# ---------------------------------------------------------------------------
# Serialization helpers (persist into CoverageVerdict.evidence JSON-as-text)
# ---------------------------------------------------------------------------
def verdict_to_evidence_list(verdict: CoverageVerdict) -> list[dict]:
    return [{"signal": e.signal, "detail": e.detail} for e in verdict.evidence]


def confidence_to_milli(confidence: float) -> int:
    """Convert [0,1] confidence to the integer 0..1000 stored on the model."""
    return int(round(_clamp01(confidence) * 1000))
