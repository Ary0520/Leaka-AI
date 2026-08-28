"""
Risk engine — deterministic business-risk scoring for graph nodes
(Requirements 3.1–3.7; design Layer 2.1).

PURE FUNCTION module (input data → output data; no I/O, no randomness), like
`fingerprint.py` and `reconciliation.py`. The coverage/graph workers map ORM
rows onto the plain inputs here and persist the `RiskResult` the engine returns.
Purity is what makes Property 4 (risk determinism) directly property-testable.

Score model (design 2.1):
  A node's score in [0, 100] is a weighted sum of factor sub-scores, each in
  [0, 1] before weighting. Every factor is recorded with its contribution and
  the evidence behind it (R3.4 explainability). The categorical level is a
  fixed banding of the numeric score.

Factors (each cites its requirement):
  - business_category weight   — billing/checkout/auth/payment high; content/nav low (R3.2)
  - graph centrality           — in-degree of depends_on / part_of_flow edges (R3.2)
  - role sensitivity           — admin / destructive actions score higher (R3.2)
  - historical failure rate    — from Memory signals, only when present (R3.3)
  - owner importance hint       — optional owner-supplied signal (R3.3)

Determinism (R3.7): pure function of (node, graph, signals); no randomness even
for ties — `rank_nodes` breaks ties by canonical_key. `manual_overrides.risk`
always wins over the computed value (R3.5), while computed factors are still
returned as evidence for transparency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Plain (ORM-free) inputs
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RiskNode:
    canonical_key: str
    node_type: str = "page"
    business_category: Optional[str] = None
    role_association: str = "unknown"
    # Authoritative human edits; only `risk` is consulted here (R3.5).
    manual_overrides: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RiskGraph:
    """
    The edges needed for centrality, in canonical-key space. Only the edge
    types that express dependency/flow membership matter for risk.
    Each edge is (source_key, target_key, edge_type).
    """
    edges: tuple = ()

    @staticmethod
    def from_edges(edges) -> "RiskGraph":
        return RiskGraph(edges=tuple((s, t, (et or "").strip().lower()) for s, t, et in edges))


@dataclass(frozen=True)
class RiskSignals:
    """
    Optional additional signals (R3.3). Absent signals are simply not counted;
    the engine records which were present so the score is explainable.
    """
    # Historical failure rate in [0.0, 1.0], or None if no history exists.
    historical_failure_rate: Optional[float] = None
    # Owner importance hint in [0.0, 1.0], or None if not supplied.
    owner_importance: Optional[float] = None


@dataclass(frozen=True)
class RiskFactor:
    name: str
    contribution: float          # points contributed to the 0..100 score
    weight: float                # this factor's max possible points
    evidence: dict               # explainable detail (R3.4)


@dataclass(frozen=True)
class RiskResult:
    level: str                   # Critical|High|Medium|Low|Trivial
    score: int                   # 0..100
    factors: tuple               # tuple[RiskFactor, ...]
    source: str                  # "computed" | "manual_override"


# ---------------------------------------------------------------------------
# Fixed, deterministic lookup tables
# ---------------------------------------------------------------------------
# Business category → base weight in [0, 1]. Unknown/other are neutral-low.
_CATEGORY_WEIGHT: dict[str, float] = {
    "payment": 1.00,
    "billing": 1.00,
    "checkout": 0.95,
    "auth": 0.90,
    "authentication": 0.90,
    "account": 0.70,
    "onboarding": 0.60,
    "search": 0.45,
    "navigation": 0.25,
    "content": 0.20,
    "unknown": 0.35,
    "other": 0.30,
}

# Role association → sensitivity weight in [0, 1].
_ROLE_WEIGHT: dict[str, float] = {
    "admin": 1.00,
    "destructive": 1.00,
    "standard": 0.45,
    "user": 0.45,
    "anonymous": 0.20,
    "unknown": 0.30,
}

# node_type nudges: destructive "action" nodes carry inherent sensitivity.
_ACTION_TYPE_BONUS: dict[str, float] = {
    "action": 0.15,
    "form": 0.05,
}

# Factor weights (max points each contributes; they sum to 100).
#
# Intrinsic drivers (category + role) are weighted so a genuinely
# revenue-critical node (e.g. billing/admin) reaches at least "High" on its own
# nature alone (R3.2), while centrality/history/importance are the boosters that
# push such a node into "Critical". A benign content/anonymous node stays low.
_W_CATEGORY = 50.0
_W_ROLE = 20.0
_W_CENTRALITY = 18.0
_W_HISTORY = 8.0
_W_IMPORTANCE = 4.0

# Centrality normalization: in-degree at/above this is treated as maximal.
_CENTRALITY_SATURATION = 5

# Score → level banding (inclusive lower bounds).
_LEVEL_BANDS = [
    (80, "Critical"),
    (60, "High"),
    (40, "Medium"),
    (20, "Low"),
    (0, "Trivial"),
]

# Edge types that count toward "things depend on this node".
_DEPENDENCY_EDGE_TYPES = {"depends_on", "part_of_flow"}


def _level_for(score: int) -> str:
    for lower, level in _LEVEL_BANDS:
        if score >= lower:
            return level
    return "Trivial"


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


# ---------------------------------------------------------------------------
# Centrality: how many nodes depend on / flow through this node (in-degree)
# ---------------------------------------------------------------------------
def _dependency_in_degree(graph: RiskGraph, node_key: str) -> int:
    """
    Count distinct source nodes that point at `node_key` via a dependency/flow
    edge. Deterministic (set of sources). This captures "many flows depend on
    this node" (R3.2).
    """
    sources: set[str] = set()
    for s, t, et in graph.edges:
        if t == node_key and et in _DEPENDENCY_EDGE_TYPES:
            sources.add(s)
    return len(sources)


# ---------------------------------------------------------------------------
# The pure scoring function
# ---------------------------------------------------------------------------
def score_node(
    node: RiskNode,
    graph: RiskGraph,
    signals: Optional[RiskSignals] = None,
) -> RiskResult:
    """
    Deterministically score a node's business risk. Pure: identical inputs
    always yield an identical RiskResult (Property 4).
    """
    signals = signals or RiskSignals()
    factors: list[RiskFactor] = []

    # ── Factor 1: business category ────────────────────────────────────────
    cat = (node.business_category or "unknown").strip().lower()
    cat_w = _CATEGORY_WEIGHT.get(cat, _CATEGORY_WEIGHT["other"])
    cat_points = _W_CATEGORY * cat_w
    factors.append(RiskFactor(
        name="business_category",
        contribution=round(cat_points, 4),
        weight=_W_CATEGORY,
        evidence={"category": cat, "category_weight": cat_w},
    ))

    # ── Factor 2: graph centrality (dependency/flow in-degree) ─────────────
    in_deg = _dependency_in_degree(graph, node.canonical_key)
    cent_norm = _clamp01(in_deg / _CENTRALITY_SATURATION)
    cent_points = _W_CENTRALITY * cent_norm
    factors.append(RiskFactor(
        name="graph_centrality",
        contribution=round(cent_points, 4),
        weight=_W_CENTRALITY,
        evidence={"dependency_in_degree": in_deg, "saturation": _CENTRALITY_SATURATION},
    ))

    # ── Factor 3: role sensitivity (+ action/form type bonus) ──────────────
    role = (node.role_association or "unknown").strip().lower()
    role_w = _ROLE_WEIGHT.get(role, _ROLE_WEIGHT["unknown"])
    ntype = (node.node_type or "page").strip().lower()
    type_bonus = _ACTION_TYPE_BONUS.get(ntype, 0.0)
    role_combined = _clamp01(role_w + type_bonus)
    role_points = _W_ROLE * role_combined
    factors.append(RiskFactor(
        name="role_sensitivity",
        contribution=round(role_points, 4),
        weight=_W_ROLE,
        evidence={"role": role, "role_weight": role_w,
                  "node_type": ntype, "type_bonus": type_bonus},
    ))

    # ── Factor 4: historical failure rate (only when present) ──────────────
    if signals.historical_failure_rate is not None:
        hist = _clamp01(float(signals.historical_failure_rate))
        hist_points = _W_HISTORY * hist
        factors.append(RiskFactor(
            name="historical_failure_rate",
            contribution=round(hist_points, 4),
            weight=_W_HISTORY,
            evidence={"present": True, "failure_rate": hist},
        ))
    else:
        factors.append(RiskFactor(
            name="historical_failure_rate",
            contribution=0.0,
            weight=_W_HISTORY,
            evidence={"present": False},
        ))

    # ── Factor 5: owner importance hint (only when present) ────────────────
    if signals.owner_importance is not None:
        imp = _clamp01(float(signals.owner_importance))
        imp_points = _W_IMPORTANCE * imp
        factors.append(RiskFactor(
            name="owner_importance",
            contribution=round(imp_points, 4),
            weight=_W_IMPORTANCE,
            evidence={"present": True, "importance": imp},
        ))
    else:
        factors.append(RiskFactor(
            name="owner_importance",
            contribution=0.0,
            weight=_W_IMPORTANCE,
            evidence={"present": False},
        ))

    computed_score = int(round(sum(f.contribution for f in factors)))
    computed_score = max(0, min(100, computed_score))
    computed_level = _level_for(computed_score)

    # ── Manual override wins (R3.5), but keep computed factors as evidence ─
    override = (node.manual_overrides or {}).get("risk") if node.manual_overrides else None
    if isinstance(override, dict) and ("level" in override or "score" in override):
        ov_score = override.get("score")
        ov_level = override.get("level")
        # If only one of level/score is provided, derive the other consistently.
        if ov_score is None and ov_level is not None:
            ov_score = _score_for_level(str(ov_level))
        if ov_score is not None:
            ov_score = max(0, min(100, int(ov_score)))
        else:
            ov_score = computed_score
        if not ov_level:
            ov_level = _level_for(ov_score)
        override_factor = RiskFactor(
            name="manual_override",
            contribution=0.0,
            weight=0.0,
            evidence={"level": ov_level, "score": ov_score,
                      "computed_level": computed_level, "computed_score": computed_score},
        )
        return RiskResult(
            level=str(ov_level),
            score=int(ov_score),
            factors=tuple([override_factor, *factors]),
            source="manual_override",
        )

    return RiskResult(
        level=computed_level,
        score=computed_score,
        factors=tuple(factors),
        source="computed",
    )


def _score_for_level(level: str) -> int:
    """Map a categorical level to a representative score (mid-band)."""
    level = (level or "").strip().lower()
    mids = {"critical": 90, "high": 70, "medium": 50, "low": 30, "trivial": 10}
    return mids.get(level, 50)


# ---------------------------------------------------------------------------
# Deterministic ranking (ties broken by canonical_key — R3.7)
# ---------------------------------------------------------------------------
def rank_nodes(
    scored: list[tuple[RiskNode, RiskResult]],
) -> list[tuple[RiskNode, RiskResult]]:
    """
    Order nodes by risk descending; ties broken by canonical_key ascending so
    ordering is fully deterministic regardless of input order (R3.7).
    """
    return sorted(
        scored,
        key=lambda pair: (-pair[1].score, pair[0].canonical_key),
    )


# ---------------------------------------------------------------------------
# Serialization helper for persistence into GraphNode.risk (JSON-as-text)
# ---------------------------------------------------------------------------
def result_to_dict(result: RiskResult) -> dict:
    return {
        "level": result.level,
        "score": result.score,
        "source": result.source,
        "factors": [
            {
                "name": f.name,
                "contribution": f.contribution,
                "weight": f.weight,
                "evidence": f.evidence,
            }
            for f in result.factors
        ],
    }
