"""
Tests for locator-memory extraction (worker._extract_locator_memories).

Proves the "preferred locator hierarchies" promise (R5.1):
  - captures locators that WORKED (from interaction actions) as a ranked
    hierarchy, most-stable strategy first (testid > id > name > role_text > xpath),
  - never fabricates: non-interaction actions and elementless actions yield
    nothing,
  - deterministic and deduplicated within a run.

Uses a minimal fake history exposing model_actions() in the browser-use 0.13.7
shape (each action dict carries `interacted_element`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.worker import _extract_locator_memories


@dataclass
class _FakeEl:
    x_path: Optional[str] = None
    ax_name: Optional[str] = None
    node_name: Optional[str] = None
    attributes: Optional[dict] = None


class _FakeHistory:
    def __init__(self, actions):
        self._actions = actions

    def model_actions(self):
        return self._actions


def test_prefers_testid_over_everything():
    el = _FakeEl(
        x_path="/html/body/div[2]/button",
        ax_name="Proceed to checkout",
        node_name="BUTTON",
        attributes={"data-testid": "checkout-btn", "id": "co", "class": "btn primary"},
    )
    hist = _FakeHistory([{"click_element_by_index": {"index": 5}, "interacted_element": el}])
    out = _extract_locator_memories(hist)
    assert len(out) == 1
    assert out[0]["hierarchy"][0] == {"strategy": "testid", "value": "checkout-btn"}
    assert out[0]["selector"] == '[data-testid="checkout-btn"]'
    # Full hierarchy retained, ordered by stability.
    strategies = [h["strategy"] for h in out[0]["hierarchy"]]
    assert strategies == ["testid", "id", "role_text", "xpath"]


def test_falls_back_to_role_text_then_xpath():
    el = _FakeEl(x_path="//a[3]", ax_name="Sign in", node_name="A", attributes={})
    hist = _FakeHistory([{"click": {}, "interacted_element": el}])
    out = _extract_locator_memories(hist)
    assert out[0]["hierarchy"][0]["strategy"] == "role_text"
    assert out[0]["hierarchy"][0]["value"] == "Sign in"
    assert out[0]["hierarchy"][-1]["strategy"] == "xpath"


def test_ignores_non_interaction_actions():
    el = _FakeEl(x_path="//div", attributes={"id": "x"})
    hist = _FakeHistory([
        {"go_to_url": {"url": "https://s.com"}, "interacted_element": None},
        {"scroll": {}, "interacted_element": el},
        {"done": {"success": True}, "interacted_element": None},
    ])
    out = _extract_locator_memories(hist)
    assert out == []


def test_skips_elementless_and_signalless():
    hist = _FakeHistory([
        {"click": {}, "interacted_element": None},              # no element
        {"click": {}, "interacted_element": _FakeEl()},          # no usable signal
    ])
    out = _extract_locator_memories(hist)
    assert out == []


def test_deduplicates_within_run_and_is_deterministic():
    el = _FakeEl(ax_name="Login", node_name="BUTTON", attributes={"id": "login"})
    actions = [
        {"click": {}, "interacted_element": el},
        {"click": {}, "interacted_element": el},  # same element again
    ]
    out1 = _extract_locator_memories(_FakeHistory(actions))
    out2 = _extract_locator_memories(_FakeHistory(list(actions)))
    assert len(out1) == 1                 # deduped
    assert out1 == out2                   # deterministic


def test_input_actions_are_captured():
    el = _FakeEl(ax_name="Email", node_name="INPUT", attributes={"name": "email"})
    hist = _FakeHistory([{"input_text": {"text": "a@b.com"}, "interacted_element": el}])
    out = _extract_locator_memories(hist)
    assert out[0]["hierarchy"][0] == {"strategy": "name", "value": "email"}
    assert out[0]["action"] == "input_text"


def test_never_raises_on_bad_history():
    class _Broken:
        def model_actions(self):
            raise RuntimeError("boom")
    assert _extract_locator_memories(_Broken()) == []
