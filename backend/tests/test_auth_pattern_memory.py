"""
Tests for auth-pattern detection (explore_worker._detect_auth_success).

Proves the "auth patterns" Memory promise (R5.1) is evidence-only:
  - detects a successful login ONLY when the trajectory cleared an auth gate
    (was on an auth page, then reached a non-auth page),
  - never fabricates: no auth transition → None,
  - the remembered payload contains NO credentials.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.explore_worker import _detect_auth_success
from app.intelligence.relationships import TrajectoryStep


def _nodes():
    return [
        SimpleNamespace(label="Login", url="https://s.com/login",
                        node_type="form", business_category="authentication"),
        SimpleNamespace(label="Dashboard", url="https://s.com/dashboard",
                        node_type="page", business_category="account"),
    ]


def test_detects_cleared_auth_gate():
    traj = [
        TrajectoryStep(url_before=None, url_after="https://s.com/login",
                       action="go_to_url", intended_url="https://s.com/login"),
        TrajectoryStep(url_before="https://s.com/login", url_after="https://s.com/dashboard",
                       action="click_element_by_index", element_text="Sign in"),
    ]
    out = _detect_auth_success(traj, _nodes())
    assert out is not None
    assert out["pattern"] == "form_login"
    assert "dashboard" in out["reached_after_auth"]
    # No credentials remembered — only the shape.
    blob = " ".join(str(v) for v in out.values()).lower()
    assert "password" not in blob and "secret" not in blob


def test_no_auth_transition_returns_none():
    # Only ever on content pages → no auth cleared.
    traj = [
        TrajectoryStep(url_before=None, url_after="https://s.com/products",
                       action="go_to_url", intended_url="https://s.com/products"),
        TrajectoryStep(url_before="https://s.com/products", url_after="https://s.com/about",
                       action="click_element_by_index"),
    ]
    assert _detect_auth_success(traj, _nodes()) is None


def test_stuck_on_auth_returns_none():
    # Reached the login page but never got past it → not a success.
    traj = [
        TrajectoryStep(url_before=None, url_after="https://s.com/login",
                       action="go_to_url", intended_url="https://s.com/login"),
        TrajectoryStep(url_before="https://s.com/login", url_after="https://s.com/login",
                       action="input_text", element_text="Email"),
    ]
    assert _detect_auth_success(traj, _nodes()) is None


def test_never_raises_on_empty():
    assert _detect_auth_success([], _nodes()) is None
    assert _detect_auth_success([], []) is None
