"""
Properties 9 & 10 for the diff→flow mapping engine (Requirements 7.7, 7.8).

  Property 9 — Mapping determinism: identical (diff, graph) inputs yield an
     identical recommendation ordering, regardless of input order.
  Property 10 — Empty vs stale: an EMPTY graph yields "no recommendations
     available", never a fabricated list.

`intelligence/mapping.py` is a PURE module → fast, DB-free property tests.
"""

from __future__ import annotations

import random

from hypothesis import given, settings, strategies as st

from app.intelligence.mapping import (
    ChangedFile, MapNode, DiffInput, map_diff, mapping_to_dict,
    GRAPH_EMPTY, GRAPH_ACTIVE, GRAPH_STALE,
    COV_COVERED, COV_UNCOVERED, COV_UNDETERMINED,
)


_KEY = st.text(alphabet="abcdef0123456789", min_size=4, max_size=8)
_URLP = st.sampled_from([None, "/", "/cart", "/checkout", "/orders/:id", "/login", "/account"])
_CAT = st.sampled_from([None, "billing", "checkout", "auth", "content", "unknown"])
_COV = st.sampled_from([COV_COVERED, COV_UNCOVERED, COV_UNDETERMINED])


@st.composite
def _node(draw) -> MapNode:
    return MapNode(
        node_id=draw(st.integers(min_value=1, max_value=99999)),
        canonical_key=draw(_KEY),
        url_pattern=draw(_URLP),
        business_category=draw(_CAT),
        risk_score=draw(st.integers(min_value=0, max_value=100)),
        risk_level=draw(st.sampled_from(["Critical", "High", "Medium", "Low", "Trivial"])),
        coverage_state=draw(_COV),
        covering_test_ids=tuple(draw(st.lists(st.integers(1, 500), max_size=4))),
    )


@st.composite
def _diff(draw) -> DiffInput:
    files = draw(st.lists(
        st.builds(ChangedFile,
                  path=st.sampled_from([
                      "src/pages/checkout.tsx", "app/routes/orders/[id].py",
                      "src/components/CartButton.tsx", "server/auth/login.py",
                      "README.md", "src/account/settings.ts",
                  ]),
                  status=st.sampled_from(["added", "modified", "removed"])),
        min_size=1, max_size=5))
    return DiffInput(changed_files=tuple(files), graph_state=GRAPH_ACTIVE)


# ---------------------------------------------------------------------------
# Property 9 — determinism / order independence
# ---------------------------------------------------------------------------
@settings(max_examples=200, deadline=None)
@given(nodes=st.lists(_node(), min_size=1, max_size=8), diff=_diff())
def test_mapping_is_deterministic_and_order_independent(nodes, diff):
    # Dedup by canonical_key so tie-break by key is well-defined.
    uniq = {n.canonical_key: n for n in nodes}
    nodes = list(uniq.values())

    r1 = map_diff(diff, nodes)
    r2 = map_diff(diff, list(reversed(nodes)))
    shuffled = nodes[:]
    random.Random(42).shuffle(shuffled)
    r3 = map_diff(diff, shuffled)

    order1 = [m.canonical_key for m in r1.mappings]
    order2 = [m.canonical_key for m in r2.mappings]
    order3 = [m.canonical_key for m in r3.mappings]
    assert order1 == order2 == order3, "mapping order depended on input order"
    assert r1.recommended_test_ids == r2.recommended_test_ids == r3.recommended_test_ids

    # Ranking respects (risk desc, canonical_key asc).
    for a, b in zip(r1.mappings, r1.mappings[1:]):
        assert (a.risk_score > b.risk_score) or (
            a.risk_score == b.risk_score and a.canonical_key <= b.canonical_key)

    # Confidence bounds + serialization stability.
    for m in r1.mappings:
        assert 0.0 <= m.confidence <= 1.0
        assert mapping_to_dict(m) == mapping_to_dict(m)


# ---------------------------------------------------------------------------
# Property 10 — empty graph → no fabricated recommendations
# ---------------------------------------------------------------------------
@settings(max_examples=100, deadline=None)
@given(diff=_diff(), nodes=st.lists(_node(), max_size=5))
def test_empty_graph_never_fabricates(diff, nodes):
    empty_diff = DiffInput(changed_files=diff.changed_files, graph_state=GRAPH_EMPTY)
    r = map_diff(empty_diff, nodes)  # even if nodes provided, EMPTY state wins
    assert r.status == "no_graph"
    assert r.mappings == ()
    assert r.recommended_test_ids == ()
    assert "explore" in r.message.lower()

    # Also: no nodes at all → same explicit no-graph result.
    r2 = map_diff(DiffInput(changed_files=diff.changed_files, graph_state=GRAPH_ACTIVE), [])
    assert r2.status == "no_graph"
    assert r2.mappings == ()


# ---------------------------------------------------------------------------
# Concrete signal behavior
# ---------------------------------------------------------------------------
def test_route_correspondence_matches():
    node = MapNode(node_id=1, canonical_key="k", url_pattern="/checkout",
                   risk_score=90, risk_level="Critical",
                   coverage_state=COV_COVERED, covering_test_ids=(7,))
    diff = DiffInput(changed_files=(ChangedFile("src/pages/checkout.tsx", "modified"),),
                     graph_state=GRAPH_ACTIVE)
    r = map_diff(diff, [node])
    assert r.status == "ok"
    assert len(r.mappings) == 1
    m = r.mappings[0]
    assert any(s.name == "route" for s in m.signals)
    assert m.recommended_test_ids == (7,)
    assert m.chain["node"] == "k"
    assert 7 in r.recommended_test_ids


def test_unrelated_file_no_mapping():
    node = MapNode(node_id=1, canonical_key="k", url_pattern="/checkout", risk_score=90)
    diff = DiffInput(changed_files=(ChangedFile("docs/README.md", "modified"),),
                     graph_state=GRAPH_ACTIVE)
    r = map_diff(diff, [node])
    assert r.mappings == ()


def test_no_coverage_warning_and_suggested_prompt():
    node = MapNode(node_id=1, canonical_key="k", url_pattern="/checkout",
                   risk_score=90, risk_level="Critical",
                   coverage_state=COV_UNCOVERED, covering_test_ids=(),
                   suggested_prompt="Test the checkout flow")
    diff = DiffInput(changed_files=(ChangedFile("src/pages/checkout.tsx"),),
                     graph_state=GRAPH_ACTIVE)
    m = map_diff(diff, [node]).mappings[0]
    assert m.no_coverage_warning is True
    assert m.suggested_prompt == "Test the checkout flow"
    assert m.recommended_test_ids == ()


def test_semantic_signal_precomputed():
    node = MapNode(node_id=1, canonical_key="k", url_pattern="/xyz",
                   risk_score=50, coverage_state=COV_COVERED, covering_test_ids=(3,))
    diff = DiffInput(
        changed_files=(ChangedFile("src/lib/pricing.ts"),),
        graph_state=GRAPH_ACTIVE,
        semantic={("src/lib/pricing.ts", "k"): 0.9},
    )
    m = map_diff(diff, [node]).mappings[0]
    assert any(s.name == "semantic" for s in m.signals)


def test_component_hint_signal():
    node = MapNode(node_id=1, canonical_key="k", url_pattern="/dashboard",
                   risk_score=40, coverage_state=COV_COVERED, covering_test_ids=(9,),
                   component_hints=("CartButton",))
    diff = DiffInput(changed_files=(ChangedFile("src/components/CartButton.tsx"),),
                     graph_state=GRAPH_ACTIVE)
    m = map_diff(diff, [node]).mappings[0]
    assert any(s.name == "component" for s in m.signals)


def test_stale_graph_conservative():
    nodes = [
        MapNode(node_id=1, canonical_key="hi", url_pattern="/pay", risk_score=90,
                risk_level="Critical", coverage_state=COV_COVERED, covering_test_ids=(1,)),
        MapNode(node_id=2, canonical_key="lo", url_pattern="/about", risk_score=10,
                risk_level="Trivial", coverage_state=COV_COVERED, covering_test_ids=(2,)),
    ]
    diff = DiffInput(changed_files=(ChangedFile("src/anything.ts"),), graph_state=GRAPH_STALE)
    r = map_diff(diff, nodes)
    assert r.status == "stale"
    # Only the high-risk node is recommended, low-confidence.
    assert [m.canonical_key for m in r.mappings] == ["hi"]
    assert r.mappings[0].confidence <= 0.5
    assert r.recommended_test_ids == (1,)
    assert "re-explore" in r.message.lower()
