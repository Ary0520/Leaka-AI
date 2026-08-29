"""
Tests for the evidence-based relationship derivation engine
(intelligence/relationships.py).

These lock in the two guarantees that make it safe to feed the graph:
  1. Determinism — identical trajectory + nodes → identical output, regardless
     of node input order (mirrors the risk/reconciliation determinism rule).
  2. Evidence-only — an edge is emitted ONLY when the trajectory demonstrably
     supports it; no trajectory evidence → no edge (never fabricated).

Plus targeted checks for each derived edge type against a realistic trajectory.
"""

from app.intelligence.relationships import (
    TrajectoryStep,
    RelNode,
    derive_relationships,
)


def _shop_nodes():
    return [
        RelNode(label="Products", url="https://shop.com/products",
                node_type="page", business_category="content"),
        RelNode(label="Cart", url="https://shop.com/cart",
                node_type="page", business_category="checkout"),
        RelNode(label="Shipping", url="https://shop.com/checkout/shipping",
                node_type="page", business_category="checkout"),
        RelNode(label="Payment", url="https://shop.com/checkout/payment",
                node_type="page", business_category="checkout"),
        RelNode(label="Login", url="https://shop.com/login",
                node_type="form", business_category="authentication"),
    ]


def _shop_trajectory():
    return [
        TrajectoryStep(url_before=None, url_after="https://shop.com/products",
                       action="go_to_url", intended_url="https://shop.com/products"),
        TrajectoryStep(url_before="https://shop.com/products", url_after="https://shop.com/cart",
                       action="click_element_by_index", element_text="View cart"),
        # Gate: intended Payment, landed on Login (redirect) → Payment depends_on Login.
        TrajectoryStep(url_before="https://shop.com/cart", url_after="https://shop.com/login",
                       action="go_to_url", intended_url="https://shop.com/checkout/payment"),
        # Clean contiguous checkout run → part_of_flow.
        TrajectoryStep(url_before="https://shop.com/login", url_after="https://shop.com/cart",
                       action="go_to_url", intended_url="https://shop.com/cart"),
        TrajectoryStep(url_before="https://shop.com/cart", url_after="https://shop.com/checkout/shipping",
                       action="click_element_by_index", element_text="Checkout"),
        TrajectoryStep(url_before="https://shop.com/checkout/shipping", url_after="https://shop.com/checkout/payment",
                       action="click_element_by_index", element_text="Continue"),
    ]


def test_depends_on_derived_from_gate_redirect():
    """A redirect to an auth page while intending another page → depends_on."""
    r = derive_relationships(_shop_trajectory(), _shop_nodes())
    assert r.depends_on.get("Payment") == ["Login"]


def test_navigates_to_derived_from_actions():
    """Navigating actions between two known pages produce navigates_to edges."""
    r = derive_relationships(_shop_trajectory(), _shop_nodes())
    assert "Cart" in r.connects_to.get("Products", [])
    assert "Shipping" in r.connects_to.get("Cart", [])


def test_part_of_flow_from_contiguous_checkout_run():
    """A contiguous run of 3+ checkout pages composes a flow."""
    r = derive_relationships(_shop_trajectory(), _shop_nodes())
    steps = r.flow_steps.get("Cart", [])
    assert "Shipping" in steps and "Payment" in steps


def test_deterministic_regardless_of_node_order():
    """Determinism: permuting node input order never changes the output."""
    nodes = _shop_nodes()
    traj = _shop_trajectory()
    base = derive_relationships(traj, nodes)
    reversed_nodes = list(reversed(nodes))
    again = derive_relationships(traj, reversed_nodes)
    assert base.connects_to == again.connects_to
    assert base.depends_on == again.depends_on
    assert base.flow_steps == again.flow_steps


def test_no_edges_without_evidence():
    """Empty trajectory → no derived edges (never fabricated)."""
    r = derive_relationships([], _shop_nodes())
    assert r.connects_to == {} and r.depends_on == {} and r.flow_steps == {}
    assert r.edges == ()


def test_no_edges_to_unknown_pages():
    """Trajectory URLs that map to no known node produce no edges."""
    traj = [
        TrajectoryStep(url_before="https://other.com/a", url_after="https://other.com/b",
                       action="click_element_by_index"),
    ]
    r = derive_relationships(traj, _shop_nodes())
    assert r.edges == ()


def test_no_self_loops_or_auth_depends_on_itself():
    """An auth node that redirects to itself must not create a self-dependency."""
    nodes = _shop_nodes()
    traj = [
        TrajectoryStep(url_before="https://shop.com/login", url_after="https://shop.com/login",
                       action="go_to_url", intended_url="https://shop.com/login"),
    ]
    r = derive_relationships(traj, nodes)
    assert r.depends_on == {}
