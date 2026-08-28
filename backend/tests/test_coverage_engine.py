"""
Properties 6 & 7 for the coverage engine (Requirements 4.1, 4.3, 4.7).

  Property 6 — Coverage monotonicity of evidence:
     adding an authoritative coverage_link never LOWERS a node's coverage
     state; removing all tests never RAISES it (→ uncovered).
  Property 7 — Coverage confidence bounds:
     every verdict confidence ∈ [0.0, 1.0].

`intelligence/coverage.py` is a PURE module → fast, DB-free property tests.
"""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from app.intelligence.coverage import (
    CoverageNode, CoverageTest, classify_node_coverage,
    rollup, gaps, detect_orphans,
    UNCOVERED, PARTIALLY_COVERED, COVERED, _STATE_RANK,
    confidence_to_milli,
)


_OPT_BOOL = st.one_of(st.none(), st.booleans())
_OPT_SIM = st.one_of(st.none(), st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
_OPT_URL = st.one_of(st.none(), st.sampled_from([
    "https://s.com/", "https://s.com/cart", "https://s.com/checkout",
    "https://s.com/orders/123", "not a url", "",
]))


@st.composite
def _test(draw, force_unlinked=False) -> CoverageTest:
    linked = False if force_unlinked else draw(st.booleans())
    return CoverageTest(
        test_case_id=draw(st.integers(min_value=1, max_value=9999)),
        target_url=draw(_OPT_URL),
        name=draw(st.one_of(st.none(), st.text(max_size=20))),
        prompt=draw(st.one_of(st.none(), st.text(max_size=30))),
        linked=linked,
        link_source=draw(st.sampled_from(["generated", "manual", None])),
        semantic_similarity=draw(_OPT_SIM),
        last_run_passed=draw(_OPT_BOOL),
    )


@st.composite
def _node(draw) -> CoverageNode:
    return CoverageNode(
        node_id=draw(st.integers(min_value=1, max_value=9999)),
        canonical_key=draw(st.text(alphabet="abcdef0123456789", min_size=4, max_size=8)),
        url_pattern=draw(st.sampled_from([None, "/", "/cart", "/checkout", "/orders/:id"])),
        business_category=draw(st.sampled_from([None, "billing", "content", "auth", "unknown"])),
        status="active",
        risk_score=draw(st.integers(min_value=0, max_value=100)),
        risk_level=draw(st.sampled_from(["Critical", "High", "Medium", "Low", "Trivial"])),
    )


# ---------------------------------------------------------------------------
# Property 7 — confidence bounds
# ---------------------------------------------------------------------------
@settings(max_examples=300, deadline=None)
@given(node=_node(), tests=st.lists(_test(), max_size=6))
def test_confidence_within_bounds(node, tests):
    v = classify_node_coverage(node, tests)
    assert 0.0 <= v.confidence <= 1.0
    assert v.state in {UNCOVERED, PARTIALLY_COVERED, COVERED}
    assert 0 <= confidence_to_milli(v.confidence) <= 1000


# ---------------------------------------------------------------------------
# Property 6 — monotonicity: adding an authoritative link never lowers state
# ---------------------------------------------------------------------------
@settings(max_examples=300, deadline=None)
@given(node=_node(), tests=st.lists(_test(force_unlinked=True), max_size=5),
       extra=_test())
def test_adding_link_never_lowers_state(node, tests, extra):
    before = classify_node_coverage(node, tests)
    # Force the extra test to be an authoritative link.
    linked_extra = CoverageTest(
        test_case_id=extra.test_case_id, target_url=extra.target_url,
        name=extra.name, prompt=extra.prompt,
        linked=True, link_source="generated",
        semantic_similarity=extra.semantic_similarity,
        last_run_passed=extra.last_run_passed,
    )
    after = classify_node_coverage(node, [*tests, linked_extra])
    assert _STATE_RANK[after.state] >= _STATE_RANK[before.state], (
        "adding an authoritative link lowered coverage state"
    )


# ---------------------------------------------------------------------------
# Property 6 (second half) — removing all tests never raises coverage
# ---------------------------------------------------------------------------
@settings(max_examples=200, deadline=None)
@given(node=_node(), tests=st.lists(_test(), min_size=1, max_size=6))
def test_removing_all_tests_yields_uncovered(node, tests):
    with_tests = classify_node_coverage(node, tests)
    without = classify_node_coverage(node, [])
    assert without.state == UNCOVERED
    assert without.confidence == 0.0
    assert _STATE_RANK[without.state] <= _STATE_RANK[with_tests.state]


# ---------------------------------------------------------------------------
# Concrete behavior checks
# ---------------------------------------------------------------------------
def test_linked_passing_is_covered_high_confidence():
    node = CoverageNode(node_id=1, canonical_key="k", url_pattern="/cart")
    t = CoverageTest(test_case_id=5, linked=True, link_source="generated", last_run_passed=True)
    v = classify_node_coverage(node, [t])
    assert v.state == COVERED
    assert v.confidence >= 0.9
    assert 5 in v.linked_test_ids


def test_linked_failing_is_covered_lower_confidence():
    node = CoverageNode(node_id=1, canonical_key="k")
    passing = classify_node_coverage(node, [CoverageTest(test_case_id=1, linked=True, last_run_passed=True)])
    failing = classify_node_coverage(node, [CoverageTest(test_case_id=1, linked=True, last_run_passed=False)])
    assert failing.state == COVERED           # flow is still tested
    assert failing.confidence < passing.confidence  # but we're less confident


def test_route_match_covers():
    node = CoverageNode(node_id=1, canonical_key="k", url_pattern="/checkout")
    t = CoverageTest(test_case_id=9, target_url="https://other.com/checkout?x=1", last_run_passed=True)
    v = classify_node_coverage(node, [t])
    assert v.state == COVERED
    assert any(e.signal == "route" for e in v.evidence)


def test_semantic_partial_vs_strong():
    node = CoverageNode(node_id=1, canonical_key="k")
    partial = classify_node_coverage(node, [CoverageTest(test_case_id=1, semantic_similarity=0.75)])
    strong = classify_node_coverage(node, [CoverageTest(test_case_id=1, semantic_similarity=0.95)])
    assert partial.state == PARTIALLY_COVERED
    assert strong.state == COVERED


def test_no_signals_is_uncovered():
    node = CoverageNode(node_id=1, canonical_key="k", url_pattern="/cart")
    t = CoverageTest(test_case_id=1, target_url="https://s.com/unrelated", semantic_similarity=0.1)
    v = classify_node_coverage(node, [t])
    assert v.state == UNCOVERED
    assert v.confidence == 0.0


def test_rollup_is_risk_weighted():
    # Critical uncovered vs Trivial covered — coverage % must reflect risk weight.
    crit = CoverageNode(node_id=1, canonical_key="a", business_category="billing",
                        risk_score=95, risk_level="Critical")
    triv = CoverageNode(node_id=2, canonical_key="b", business_category="content",
                        risk_score=5, risk_level="Trivial")
    verdicts = {
        1: classify_node_coverage(crit, []),  # uncovered
        2: classify_node_coverage(triv, [CoverageTest(test_case_id=1, linked=True, last_run_passed=True)]),
    }
    rl = rollup(verdicts, [crit, triv])
    app = rl["application"]
    # Covered weight (trivial, weight 6) over total (6 + 96) → small %.
    assert app.percent < 20.0
    assert app.covered_count == 1
    assert app.uncovered_count == 1


def test_gaps_ranked_by_risk():
    n1 = CoverageNode(node_id=1, canonical_key="a", risk_score=30, risk_level="Low")
    n2 = CoverageNode(node_id=2, canonical_key="b", risk_score=90, risk_level="Critical")
    verdicts = {1: classify_node_coverage(n1, []), 2: classify_node_coverage(n2, [])}
    g = gaps(verdicts, [n1, n2])
    assert [x.node_id for x in g] == [2, 1]  # highest risk first


def test_orphan_detection():
    links = [(10, 1), (11, 2), (12, 3)]
    stale = {2, 3}
    assert detect_orphans(links, stale) == [(11, 2), (12, 3)]
