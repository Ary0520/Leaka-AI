"""
Relationship derivation engine — turn an explore run's OBSERVED trajectory into
typed graph-relationship evidence (Requirements 2.2, 2.3, 2.4).

WHY THIS EXISTS
---------------
The exploration agent reliably captures each node's identity (label/url/type)
but is unreliable at filling the *relationship* fields (`connects_to`,
`depends_on`, `flow_steps`) in its structured output — it simply forgets them.
Those relationships are the single most valuable part of the graph for an
enterprise QA lead: they answer "if this breaks, what else breaks?" (blast
radius) and feed graph-centrality risk.

Rather than depend on the model's diligence, this module DERIVES relationship
evidence from what the agent DEMONSTRABLY did during the run — its ordered
browser trajectory (per-step url + action + the element it interacted with).
Every derived edge cites the concrete evidence that produced it, so it is
explainable and auditable (R2.5) and NEVER fabricated (R2.2/R2.3): if the
trajectory shows no evidence for a relationship, none is emitted.

PURITY
------
Like `fingerprint.py` / `reconciliation.py` / `risk.py`, this is a PURE module:
input data (trajectory + discovered nodes) → output data (derived edges). No
I/O, no randomness, fully deterministic and unit/property-testable. The
`explore_worker` does all the I/O: it extracts the trajectory from the
browser-use `AgentHistoryList` and feeds it here, then merges the results into
the AppMapNode relationship fields as a FALLBACK (an LLM-provided value always
wins over a derived one).

EVIDENCE MODEL (what maps to what)
----------------------------------
- navigates_to : the agent performed a navigating action (click / go_to_url)
                 on page A and the browser URL changed to page B. This is the
                 real, directed navigation structure — stronger and better
                 directed than mere visit adjacency.
- depends_on   : the agent tried to reach page X but the app GATED it — the URL
                 landed on an authentication page instead (a redirect to login/
                 signup). That is hard evidence that X depends_on the auth node.
                 This is the "checkout redirected me to log in" signal, detected
                 from the trajectory instead of hoping the model reported it.
- part_of_flow : a contiguous run of navigations through 3+ distinct pages that
                 stays within a single multi-step business area (checkout /
                 onboarding) is evidence those pages compose a flow. Conservative
                 by design — only emitted for genuinely multi-step business
                 categories, never for arbitrary browsing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .fingerprint import normalize_url


# ---------------------------------------------------------------------------
# Inputs (plain, ORM-free) — the worker builds these from AgentHistoryList.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TrajectoryStep:
    """
    One observed step of the explore agent.

    url_before : the browser URL at the START of this step (state.url of the
                 PRIOR step; None for the first step).
    url_after  : the browser URL AFTER this step's action resolved (this step's
                 state.url). This is where the action actually LANDED — so a
                 redirect/gate is visible as url_after != the intended target.
    action     : the primary action name (e.g. 'go_to_url', 'click_element_by_
                 index', 'input_text', 'done'). Best-effort; may be ''.
    intended_url : if the action carried an explicit target URL (go_to_url), the
                 normalized target the agent MEANT to reach; else None.
    element_text : visible text of the element the agent interacted with, if any
                 (e.g. 'Proceed to checkout'). Used only as human evidence.
    """
    url_before: Optional[str]
    url_after: Optional[str]
    action: str = ""
    intended_url: Optional[str] = None
    element_text: Optional[str] = None


@dataclass(frozen=True)
class RelNode:
    """A discovered node as this engine needs to see it (label + url + category)."""
    label: str
    url: Optional[str] = None
    node_type: str = "page"
    business_category: Optional[str] = None


@dataclass(frozen=True)
class DerivedEdge:
    """
    A single derived relationship, in NODE-LABEL space (the AppMapNode fields
    are label lists), with the concrete evidence that produced it.
    """
    source_label: str
    target_label: str
    edge_type: str                    # navigates_to | depends_on | part_of_flow
    evidence: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RelationshipResult:
    """
    Derived relationships grouped for the worker to merge into AppMapNode fields.

    connects_to  : {source_label -> [target_labels]}   (navigates_to)
    depends_on   : {source_label -> [dependency_labels]}
    flow_steps   : {flow_label   -> [ordered step_labels]}
    edges        : the flat, explainable list (kept for provenance/tests)
    """
    connects_to: dict
    depends_on: dict
    flow_steps: dict
    edges: tuple


# ---------------------------------------------------------------------------
# Categories that represent authentication gates and multi-step flows.
# Kept in sync with explore_worker._CATEGORY_KEYWORDS semantics.
# ---------------------------------------------------------------------------
_AUTH_CATEGORIES = {"authentication", "auth"}
# URL/label keywords that mark an auth page even when category wasn't set.
_AUTH_KEYWORDS = (
    "login", "signin", "sign-in", "sign_in", "signup", "sign-up", "sign_up",
    "register", "auth", "session/new", "account/login",
)
# Business areas that are genuinely multi-step (eligible for part_of_flow).
_FLOW_CATEGORIES = {"checkout", "billing", "onboarding"}

_NAVIGATING_ACTIONS = {"go_to_url", "click_element_by_index", "click", "open_tab", "switch_tab"}
_MIN_FLOW_STEPS = 3          # a flow needs at least this many distinct pages


def _norm(u: Optional[str]) -> str:
    """Normalize a URL to its stable path signature (reuses fingerprint logic)."""
    return normalize_url(u)


def _looks_like_auth(node: RelNode) -> bool:
    cat = (node.business_category or "").strip().lower()
    if cat in _AUTH_CATEGORIES:
        return True
    hay = f"{node.url or ''} {node.label or ''}".lower()
    return any(k in hay for k in _AUTH_KEYWORDS)


# ---------------------------------------------------------------------------
# The pure derivation function
# ---------------------------------------------------------------------------
def derive_relationships(
    steps: list[TrajectoryStep],
    nodes: list[RelNode],
) -> RelationshipResult:
    """
    Derive navigates_to / depends_on / part_of_flow evidence from the observed
    trajectory. Pure & deterministic: identical inputs → identical output, with
    all lists in stable order.

    Never fabricates: an edge is emitted ONLY when a concrete trajectory event
    supports it. When the trajectory is empty or maps to no known node, the
    result is empty.
    """
    # Map normalized-path -> node label (first node with that path wins, stable).
    label_by_path: dict[str, str] = {}
    node_by_label: dict[str, RelNode] = {}
    for n in nodes:
        node_by_label.setdefault((n.label or "").strip(), n)
        p = _norm(n.url)
        if p and p not in label_by_path:
            label_by_path[p] = (n.label or "").strip()

    auth_labels = {(n.label or "").strip() for n in nodes if _looks_like_auth(n)}

    edges: list[DerivedEdge] = []
    seen: set = set()  # (src, tgt, type) dedup

    def _emit(src: str, tgt: str, etype: str, evidence: dict) -> None:
        if not src or not tgt or src == tgt:
            return
        key = (src, tgt, etype)
        if key in seen:
            return
        seen.add(key)
        edges.append(DerivedEdge(source_label=src, target_label=tgt,
                                 edge_type=etype, evidence=evidence))

    # Ordered label trail of pages the agent actually stood on (for flow + nav).
    label_trail: list[tuple[int, str]] = []  # (step_index, label)
    for i, s in enumerate(steps):
        lbl = label_by_path.get(_norm(s.url_after))
        if lbl:
            if not label_trail or label_trail[-1][1] != lbl:
                label_trail.append((i, lbl))

    # ── navigates_to + depends_on from per-step action transitions ─────────
    for i, s in enumerate(steps):
        if s.action and s.action not in _NAVIGATING_ACTIONS:
            continue
        src_label = label_by_path.get(_norm(s.url_before))
        dst_label = label_by_path.get(_norm(s.url_after))

        # depends_on (GATE): the agent intended a specific non-auth target but
        # the browser landed on an auth page → the intended node depends_on auth.
        if s.intended_url:
            intended_label = label_by_path.get(_norm(s.intended_url))
            landed = node_by_label.get(dst_label) if dst_label else None
            if (
                intended_label
                and landed is not None
                and _looks_like_auth(landed)
                and intended_label not in auth_labels
                and dst_label != intended_label
            ):
                _emit(
                    intended_label, dst_label, "depends_on",
                    {
                        "reason": "gated_redirect_to_auth",
                        "intended_url": s.intended_url,
                        "landed_url": s.url_after,
                        "step": i,
                    },
                )
                # A gated attempt is not also a clean navigation; skip nav emit.
                continue

        # navigates_to: a navigating action that moved between two known pages.
        if src_label and dst_label and src_label != dst_label:
            _emit(
                src_label, dst_label, "navigates_to",
                {
                    "reason": "observed_navigation",
                    "action": s.action,
                    "element_text": (s.element_text or None),
                    "step": i,
                },
            )

    # ── part_of_flow from contiguous multi-step runs in a flow business area ─
    # Look at the ordered page trail; a maximal run of DISTINCT pages that all
    # sit in a flow-eligible category and is >= _MIN_FLOW_STEPS long is evidence
    # of a flow composed of those steps.
    trail_labels = [lbl for _, lbl in label_trail]
    i = 0
    while i < len(trail_labels):
        run: list[str] = []
        j = i
        while j < len(trail_labels):
            lbl = trail_labels[j]
            n = node_by_label.get(lbl)
            cat = (n.business_category or "").strip().lower() if n else ""
            if cat in _FLOW_CATEGORIES and lbl not in run:
                run.append(lbl)
                j += 1
            else:
                break
        if len(run) >= _MIN_FLOW_STEPS:
            # Name the flow after its dominant category's first step; the worker
            # decides whether to attach steps to an existing flow node. We emit
            # ordered step→step navigation-style membership using the first page
            # as the flow anchor label.
            flow_anchor = run[0]
            for step_lbl in run:
                _emit(flow_anchor, step_lbl, "part_of_flow",
                      {"reason": "contiguous_flow_run", "steps": list(run)})
            i = j
        else:
            i += 1

    # ── Group into the label-list shape the worker merges into AppMapNode ──
    connects_to: dict[str, list[str]] = {}
    depends_on: dict[str, list[str]] = {}
    flow_steps: dict[str, list[str]] = {}
    for e in edges:
        if e.edge_type == "navigates_to":
            connects_to.setdefault(e.source_label, [])
            if e.target_label not in connects_to[e.source_label]:
                connects_to[e.source_label].append(e.target_label)
        elif e.edge_type == "depends_on":
            depends_on.setdefault(e.source_label, [])
            if e.target_label not in depends_on[e.source_label]:
                depends_on[e.source_label].append(e.target_label)
        elif e.edge_type == "part_of_flow":
            flow_steps.setdefault(e.source_label, [])
            if e.target_label not in flow_steps[e.source_label]:
                flow_steps[e.source_label].append(e.target_label)

    return RelationshipResult(
        connects_to=connects_to,
        depends_on=depends_on,
        flow_steps=flow_steps,
        edges=tuple(edges),
    )
