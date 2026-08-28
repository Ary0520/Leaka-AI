"""
Property 4 — Risk determinism (Requirements 3.7).

  "score_node(n, G, S) == score_node(n, G, S) for all inputs; permuting
   evaluation order of equal-risk nodes never changes any score."

`intelligence/risk.py` is a PURE module, so these are fast, DB-free
property-based tests.
"""

from __future__ import annotations

import random

from hypothesis import given, settings, strategies as st

from app.intelligence.risk import (
    RiskNode, RiskGraph, RiskSignals,
    score_node, rank_nodes, result_to_dict,
)


_CATEGORIES = st.sampled_from([
    None, "payment", "billing", "checkout", "auth", "account",
    "onboarding", "search", "navigation", "content", "unknown", "other",
    "SomeUnknownCat",
])
_ROLES = st.sampled_from(["admin", "destructive", "standard", "user", "anonymous", "unknown"])
_TYPES = st.sampled_from(["page", "form", "flow", "action", "role"])
_KEY = st.text(alphabet="abcdef0123456789", min_size=4, max_size=8)


@st.composite
def _node(draw) -> RiskNode:
    return RiskNode(
        canonical_key=draw(_KEY),
        node_type=draw(_TYPES),
        business_category=draw(_CATEGORIES),
        role_association=draw(_ROLES),
    )


_OPT_RATE = st.one_of(st.none(), st.floats(min_value=0.0, max_value=1.0, allow_nan=False))


@st.composite
def _signals(draw) -> RiskSignals:
    return RiskSignals(
        historical_failure_rate=draw(_OPT_RATE),
        owner_importance=draw(_OPT_RATE),
    )


@st.composite
def _graph_for(draw, node_key: str) -> RiskGraph:
    others = draw(st.lists(_KEY, min_size=0, max_size=6))
    etypes = st.sampled_from(["depends_on", "part_of_flow", "navigates_to", "contains"])
    edges = []
    for o in others:
        edges.append((o, node_key, draw(etypes)))
    # add some noise edges not pointing at the node
    for _ in range(draw(st.integers(min_value=0, max_value=4))):
        edges.append((draw(_KEY), draw(_KEY), draw(etypes)))
    return RiskGraph.from_edges(edges)


# ---------------------------------------------------------------------------
# Property 4a — pure determinism: identical inputs → identical output
# ---------------------------------------------------------------------------
@settings(max_examples=200, deadline=None)
@given(node=_node(), signals=_signals(), data=st.data())
def test_score_is_deterministic(node, signals, data):
    graph = data.draw(_graph_for(node.canonical_key))
    r1 = score_node(node, graph, signals)
    r2 = score_node(node, graph, signals)
    assert r1 == r2
    assert result_to_dict(r1) == result_to_dict(r2)
    assert 0 <= r1.score <= 100
    assert r1.level in {"Critical", "High", "Medium", "Low", "Trivial"}


# ---------------------------------------------------------------------------
# Property 4b — edge order independence (centrality is a set count)
# ---------------------------------------------------------------------------
@settings(max_examples=150, deadline=None)
@given(node=_node(), signals=_signals(), data=st.data())
def test_score_independent_of_edge_order(node, signals, data):
    graph = data.draw(_graph_for(node.canonical_key))
    edges = list(graph.edges)
    shuffled = edges[:]
    random.Random(12345).shuffle(shuffled)
    r_orig = score_node(node, RiskGraph(edges=tuple(edges)), signals)
    r_shuf = score_node(node, RiskGraph(edges=tuple(shuffled)), signals)
    assert r_orig.score == r_shuf.score
    assert r_orig.level == r_shuf.level


# ---------------------------------------------------------------------------
# Property 4c — ranking permutation invariance + deterministic tie-break
# ---------------------------------------------------------------------------
@settings(max_examples=100, deadline=None)
@given(nodes=st.lists(_node(), min_size=1, max_size=8), signals=_signals())
def test_ranking_is_permutation_invariant(nodes, signals):
    # Deduplicate by canonical_key so tie-break by key is well-defined.
    uniq = {n.canonical_key: n for n in nodes}
    nodes = list(uniq.values())
    empty = RiskGraph()

    scored = [(n, score_node(n, empty, signals)) for n in nodes]
    ranked_a = rank_nodes(scored)

    shuffled = scored[:]
    random.Random(999).shuffle(shuffled)
    ranked_b = rank_nodes(shuffled)

    # Same order of canonical_keys regardless of input permutation.
    assert [n.canonical_key for n, _ in ranked_a] == [n.canonical_key for n, _ in ranked_b]

    # Ranking respects (score desc, canonical_key asc).
    for (na, ra), (nb, rb) in zip(ranked_a, ranked_a[1:]):
        assert (ra.score > rb.score) or (
            ra.score == rb.score and na.canonical_key <= nb.canonical_key
        )


# ---------------------------------------------------------------------------
# Manual-override supremacy over computed risk (R3.5)
# ---------------------------------------------------------------------------
def test_manual_override_wins():
    node = RiskNode(
        canonical_key="k1", node_type="page", business_category="content",
        role_association="anonymous",
        manual_overrides={"risk": {"level": "Critical", "score": 99}},
    )
    r = score_node(node, RiskGraph(), RiskSignals())
    assert r.source == "manual_override"
    assert r.level == "Critical"
    assert r.score == 99
    # Computed factors preserved as evidence for transparency.
    assert any(f.name == "business_category" for f in r.factors)
    assert r.factors[0].name == "manual_override"


def test_override_level_only_derives_score():
    node = RiskNode(
        canonical_key="k2", business_category="content",
        manual_overrides={"risk": {"level": "High"}},
    )
    r = score_node(node, RiskGraph(), RiskSignals())
    assert r.level == "High"
    assert 0 <= r.score <= 100


# ---------------------------------------------------------------------------
# Concrete sanity: high-risk vs low-risk banding
# ---------------------------------------------------------------------------
def test_billing_admin_scores_higher_than_content_anonymous():
    billing = RiskNode(canonical_key="a", node_type="form",
                       business_category="billing", role_association="admin")
    content = RiskNode(canonical_key="b", node_type="page",
                       business_category="content", role_association="anonymous")
    rb = score_node(billing, RiskGraph(), RiskSignals())
    rc = score_node(content, RiskGraph(), RiskSignals())
    assert rb.score > rc.score
    assert rb.level in {"Critical", "High"}
    assert rc.level in {"Trivial", "Low"}


def test_centrality_raises_score():
    node = RiskNode(canonical_key="hub", business_category="content", role_association="anonymous")
    isolated = score_node(node, RiskGraph(), RiskSignals())
    # Five distinct nodes depend on "hub".
    edges = [(f"n{i}", "hub", "depends_on") for i in range(5)]
    central = score_node(node, RiskGraph.from_edges(edges), RiskSignals())
    assert central.score > isolated.score
