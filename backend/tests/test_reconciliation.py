"""
Properties 1, 3, 5 for the reconciliation engine (Requirements 1.6, 1.10,
2.7, 3.5, 10.3).

`intelligence/reconciliation.py` is a PURE module, so these are fast,
DB-free property-based tests.

  Property 1 — Reconciliation idempotency:
     reconcile(reconcile(G, D), D) adds no new nodes and yields an empty
     snapshot diff.
  Property 3 — Snapshots are append-only:
     a reconcile never reduces the count of prior members it was given and
     never mutates a frozen member row (we assert the engine returns NEW
     member lists and leaves inputs untouched, and that a matched node's
     prior snapshot member is preserved verbatim in history).
  Property 5 — Manual-override supremacy:
     after reconcile, every field present in a matched node's manual_overrides
     equals the override value in the resulting NodeChange.
"""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from app.intelligence.fingerprint import Discovery, NodeSignatures, compute_canonical_key
from app.intelligence import reconciliation as R


# ---------------------------------------------------------------------------
# Strategies — generate plausible discoveries
# ---------------------------------------------------------------------------
_NODE_TYPES = st.sampled_from(["page", "form", "flow", "action", "role"])
_LABEL = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    min_size=1,
    max_size=20,
).filter(lambda s: s.strip() != "")

# A url path (or None for URL-less nodes). Keep segments plain so identity is
# stable and predictable.
_SEGMENT = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=8)
_URL = st.one_of(
    st.none(),
    st.builds(
        lambda segs: "https://app.example.com/" + "/".join(segs),
        st.lists(_SEGMENT, min_size=1, max_size=3),
    ),
)


@st.composite
def _discovery(draw) -> Discovery:
    return Discovery(
        node_type=draw(_NODE_TYPES),
        label=draw(_LABEL),
        url=draw(_URL),
        description=draw(st.one_of(st.none(), _LABEL)),
    )


_DISCOVERIES = st.lists(_discovery(), min_size=1, max_size=8)


# ---------------------------------------------------------------------------
# Helper: turn a ReconcileResult into the ExistingNode inputs for a next run
# (this is exactly what the worker would persist then re-load).
# ---------------------------------------------------------------------------
def _result_to_existing_nodes(result: R.ReconcileResult) -> list[R.ExistingNode]:
    nodes: list[R.ExistingNode] = []
    for c in result.nodes:
        status = "stale" if c.change == "staled" else "active"
        nodes.append(
            R.ExistingNode(
                canonical_key=c.canonical_key,
                node_type=c.node_type,
                label=c.label,
                url_pattern=c.url_pattern,
                business_category=c.business_category,
                role_association=c.role_association,
                status=status,
                signatures=NodeSignatures(
                    node_type=c.node_type,
                    url_signature=c.fingerprint.url_signature,
                    text_signature=c.fingerprint.text_signature,
                    dom_signature=c.fingerprint.dom_signature,
                    aria_signature=c.fingerprint.aria_signature,
                ),
            )
        )
    return nodes


# ---------------------------------------------------------------------------
# Property 1 — idempotency
# ---------------------------------------------------------------------------
@settings(max_examples=150, deadline=None)
@given(discoveries=_DISCOVERIES)
def test_reconcile_idempotent(discoveries):
    """reconcile(reconcile(∅, D), D) creates no new nodes and an empty diff."""
    first = R.reconcile([], [], discoveries)

    existing = _result_to_existing_nodes(first)
    second = R.reconcile(existing, [], discoveries, previous_members=first.members)

    # No node created on the second pass.
    assert second.added_nodes == [], "idempotency violated: second run added nodes"
    # Every node in the second pass matched (nothing staled either, since we
    # re-observed exactly the same discoveries).
    assert all(n.change == "matched" for n in second.nodes), (
        "second run should MATCH every re-observed node"
    )
    # Snapshot diff vs the previous (first) snapshot is empty.
    counts = second.diff_summary["counts"]
    assert counts["added"] == 0
    assert counts["removed"] == 0
    assert counts["changed"] == 0


# ---------------------------------------------------------------------------
# Property 3 — snapshots append-only / inputs never mutated
# ---------------------------------------------------------------------------
@settings(max_examples=150, deadline=None)
@given(discoveries=_DISCOVERIES)
def test_snapshots_append_only(discoveries):
    """
    A reconcile returns a fresh member list and never fewer members than the
    number of distinct identities it knows about; prior members handed in are
    returned unmutated (frozen dataclasses guarantee immutability).
    """
    first = R.reconcile([], [], discoveries)
    prev_members = list(first.members)  # snapshot of the input we pass in
    prev_ids = [id(m) for m in prev_members]

    existing = _result_to_existing_nodes(first)
    second = R.reconcile(existing, [], discoveries, previous_members=prev_members)

    # The previous members list we passed in is untouched (append-only history).
    assert [id(m) for m in prev_members] == prev_ids
    assert len(prev_members) == len(first.members)

    # The new snapshot preserves at least every identity from the first.
    first_keys = {m.canonical_key for m in first.members}
    second_keys = {m.canonical_key for m in second.members}
    assert first_keys <= second_keys, "a snapshot dropped a previously-known identity"

    # SnapshotMemberState is frozen — mutation attempts must fail.
    import dataclasses
    for m in second.members:
        assert dataclasses.is_dataclass(m)
        try:
            m.label = "mutated"  # type: ignore[misc]
            raise AssertionError("frozen member was mutable")
        except dataclasses.FrozenInstanceError:
            pass


# ---------------------------------------------------------------------------
# Property 5 — manual-override supremacy
# ---------------------------------------------------------------------------
@settings(max_examples=150, deadline=None)
@given(
    discoveries=_DISCOVERIES,
    override_type=st.sampled_from(["page", "form", "flow", "action", "role"]),
    override_cat=st.sampled_from(["billing", "auth", "checkout", "content", "unknown"]),
    override_role=st.sampled_from(["admin", "standard", "anonymous", "unknown"]),
)
def test_manual_override_supremacy(discoveries, override_type, override_cat, override_role):
    """
    After reconcile, any field present in a matched node's manual_overrides
    equals the override value — a re-explore never reverts a human correction.
    """
    first = R.reconcile([], [], discoveries)

    # Attach manual overrides to every node, then re-run with the same discoveries.
    overrides = {
        "node_type": override_type,
        "business_category": override_cat,
        "role_association": override_role,
    }
    existing = [
        R.ExistingNode(
            canonical_key=c.canonical_key,
            node_type=c.node_type,
            label=c.label,
            url_pattern=c.url_pattern,
            business_category=c.business_category,
            role_association=c.role_association,
            status="active",
            signatures=NodeSignatures(
                node_type=c.node_type,
                url_signature=c.fingerprint.url_signature,
                text_signature=c.fingerprint.text_signature,
            ),
            manual_overrides=overrides,
        )
        for c in first.nodes
    ]

    second = R.reconcile(existing, [], discoveries, previous_members=first.members)

    matched = [n for n in second.nodes if n.change == "matched"]
    assert matched, "expected matched nodes to apply overrides to"
    for n in matched:
        assert n.node_type == override_type
        assert n.business_category == override_cat
        assert n.role_association == override_role


# ---------------------------------------------------------------------------
# Concrete examples
# ---------------------------------------------------------------------------
def test_new_then_stale_then_reappear():
    """A node observed, then absent (staled), then re-observed (re-activated)."""
    d_login = Discovery(node_type="page", label="Login", url="https://s.com/login")
    d_cart = Discovery(node_type="page", label="Cart", url="https://s.com/cart")

    r1 = R.reconcile([], [], [d_login, d_cart])
    assert {n.change for n in r1.nodes} == {"new"}
    assert r1.node_count == 2

    # Second run only sees login → cart must be staled, not deleted.
    existing = _result_to_existing_nodes(r1)
    r2 = R.reconcile(existing, [], [d_login], previous_members=r1.members)
    changes = {n.canonical_key: n.change for n in r2.nodes}
    cart_key = compute_canonical_key(d_cart)
    login_key = compute_canonical_key(d_login)
    assert changes[login_key] == "matched"
    assert changes[cart_key] == "staled"
    # Snapshot still contains BOTH keys (staled is retained, not dropped).
    assert {m.canonical_key for m in r2.members} == {login_key, cart_key}
    # Active node count is now 1 (cart is stale).
    assert r2.node_count == 1
    # The cart identity is RETAINED in the snapshot (append-only history), so
    # it is not "removed"; going active→stale is a metadata CHANGE.
    assert r2.diff_summary["counts"]["removed"] == 0
    assert cart_key in r2.diff_summary["changed"]
    # And the frozen cart member now carries status "stale".
    cart_member = next(m for m in r2.members if m.canonical_key == cart_key)
    assert cart_member.status == "stale"


def test_edge_dedup_and_stale():
    """Edges dedup by (source,target,type); un-re-evidenced edges stale."""
    a, b = "keyA", "keyB"
    ev = [R.EdgeEvidence(source_key=a, target_key=b, edge_type="navigates_to")]
    r1 = R.reconcile([], [], [Discovery("page", "A", "https://s.com/a")], edge_evidence=ev)
    assert len([e for e in r1.edges if e.change == "new"]) == 1

    existing_edges = [
        R.ExistingEdge(source_key=e.source_key, target_key=e.target_key, edge_type=e.edge_type)
        for e in r1.edges
        if e.change != "staled"
    ]
    # Re-run with SAME evidence → matched, no new edge.
    r2 = R.reconcile(
        [], existing_edges, [Discovery("page", "A", "https://s.com/a")], edge_evidence=ev
    )
    assert [e.change for e in r2.edges] == ["matched"]

    # Re-run with NO evidence → the edge is staled (not deleted).
    r3 = R.reconcile([], existing_edges, [Discovery("page", "A", "https://s.com/a")])
    assert [e.change for e in r3.edges] == ["staled"]


def test_no_edges_fabricated_without_evidence():
    """The flat explorer provides no edge evidence → engine emits no edges."""
    r = R.reconcile([], [], [Discovery("page", "Home", "https://s.com/")])
    assert r.edges == []
    assert r.edge_count == 0
