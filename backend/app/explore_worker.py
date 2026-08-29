"""
Explore worker — Application Intelligence.

Runs a browser-use Agent in "explore" mode against an application to
autonomously discover its pages, forms, and user flows, then persists a
structured application map.

This module is DELIBERATELY separate from worker.py. It reuses the same proven
patterns (Windows event-loop policy, fresh ProactorEventLoop per run, live-step
callback) but writes ONLY to the Application / ExploreRun / AppMapNode tables.
It never imports or mutates the test-run execution path, so it cannot affect
existing QA test runs.
"""

import asyncio
import json
import logging
import sys
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("revguard.explore")

# ── CRITICAL WINDOWS FIX (same as worker.py) ────────────────────────────────
# ProactorEventLoop is required on Windows to spawn Chromium subprocesses.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
# ────────────────────────────────────────────────────────────────────────────

from .celery_app import celery_app
from .database import SessionLocal
from .llm import get_llm
from .models import (
    Application,
    AppMapNode,
    ExploreRun,
    ExploreRunStatus,
)


# ---------------------------------------------------------------------------
# Structured output schema — what the exploration agent must return.
# browser-use 0.13.7 supports Agent(output_model_schema=...) and exposes
# history.structured_output. This turns the map into validated data, not text.
# ---------------------------------------------------------------------------
class DiscoveredNode(BaseModel):
    node_type: str = Field(description="One of: page, form, flow")
    label: str = Field(description="Short human name, e.g. 'Checkout' or 'Login form'")
    url: Optional[str] = Field(default=None, description="URL where this lives, if known")
    description: Optional[str] = Field(default=None, description="What it does / contains")
    business_category: Optional[str] = Field(
        default=None,
        description=(
            "The business function this node serves. Choose the SINGLE best fit "
            "ONLY from: authentication, billing, checkout, onboarding, account, "
            "navigation, content, search, other. Use 'other' if genuinely unsure "
            "— do NOT guess a specific category you didn't observe evidence for."
        ),
    )
    connects_to: list[str] = Field(
        default_factory=list,
        description=(
            "The exact `label`s of OTHER nodes in this map that this node links "
            "to or leads into, based on navigation you actually observed (e.g. a "
            "'Cart' page has a button leading to 'Checkout' → connects_to: "
            "['Checkout']). Only include real, observed navigation. Empty if none."
        ),
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description=(
            "The exact `label`s of OTHER nodes that are a PRECONDITION for this "
            "one — i.e. you HIT A GATE that required them. Only include a "
            "dependency if you ACTUALLY OBSERVED the requirement (e.g. Checkout "
            "redirected you to log in → depends_on: ['Login']; Apply Coupon "
            "required items in the cart → depends_on: ['Cart']). Do NOT guess or "
            "assume dependencies you didn't encounter. Empty if you observed none."
        ),
    )
    flow_steps: list[str] = Field(
        default_factory=list,
        description=(
            "ONLY for node_type == 'flow': the ordered `label`s of the nodes that "
            "make up this multi-step flow (e.g. a 'Checkout' flow → flow_steps: "
            "['Cart', 'Shipping', 'Payment', 'Confirmation']). Use the exact "
            "labels of nodes in this map. Empty for non-flow nodes."
        ),
    )
    suggested_prompt: Optional[str] = Field(
        default=None,
        description="A natural-language QA test prompt that would exercise this node",
    )


class ApplicationMap(BaseModel):
    nodes: list[DiscoveredNode] = Field(default_factory=list)
    summary: Optional[str] = Field(
        default=None, description="One-paragraph summary of what the application is"
    )


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------
def _update_explore_status(
    job_id: str,
    *,
    status: Optional[ExploreRunStatus] = None,
    patch: Optional[dict[str, Any]] = None,
) -> None:
    db = SessionLocal()
    try:
        run = db.query(ExploreRun).filter(ExploreRun.job_id == job_id).first()
        if not run:
            return
        if status is not None:
            run.status = status
        if patch:
            for key, value in patch.items():
                if hasattr(run, key):
                    setattr(run, key, value)
        db.commit()
    finally:
        db.close()


def _explore_memory_hint(application_id: int, owner_id: Optional[str]) -> Optional[str]:
    """
    Build an app-level Memory hint (auth patterns Leaka learned) for the explore
    task. Best-effort — returns None on any failure, never breaks the explore.
    """
    db = SessionLocal()
    try:
        from . import memory as MEM
        items = MEM.retrieve(db, application_id, owner_id=owner_id, kind="auth_pattern", k=3)
        if not items:
            return None
        lines = []
        for it in items:
            hint = it.payload.get("summary") or it.payload.get("pattern")
            if hint:
                lines.append(f"- {hint}")
        if not lines:
            return None
        return "LEAKA MEMORY (auth patterns learned previously):\n" + "\n".join(lines[:3])
    except Exception:
        return None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Deterministic enrichment (fallback when the LLM leaves fields empty).
# The exploration agent reliably captures url/label/visit-order but often does
# NOT fill business_category / connects_to. Rather than depend on the model's
# diligence, we DERIVE those signals from observed evidence:
#   - category: matched from URL/label keywords (only when a keyword genuinely
#     applies — never a forced guess).
#   - connects_to: from the ORDERED visited-URL sequence (consecutive visits are
#     real observed navigation → navigates_to edges), per design R1.
# These run only as a FALLBACK: an LLM-provided value always wins.
# ---------------------------------------------------------------------------
_CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    # (category, keywords) — first match wins; order = specificity.
    ("authentication", ("login", "signin", "sign-in", "signup", "sign-up", "register", "auth", "password", "account/login")),
    ("billing", ("checkout", "payment", "pay", "billing", "invoice", "card")),
    ("checkout", ("cart", "basket", "bag", "order")),
    ("account", ("account", "profile", "settings", "dashboard", "my-")),
    ("onboarding", ("onboard", "welcome", "get-started", "setup")),
    ("search", ("search", "query", "find")),
    ("content", ("product", "shop", "store", "item", "catalog", "collection", "blog", "article")),
    ("navigation", ("home", "about", "contact", "help", "faq", "index")),
]


def _infer_category(url: Optional[str], label: Optional[str]) -> Optional[str]:
    """Infer a business_category from URL + label keywords. None if no match."""
    hay = f"{(url or '')} {(label or '')}".lower()
    for cat, kws in _CATEGORY_KEYWORDS:
        if any(k in hay for k in kws):
            return cat
    return None


def _normalize_url_path(u: Optional[str]) -> str:
    """Path-only, lowercased, trailing-slash-stripped — for matching visits→nodes."""
    if not u:
        return ""
    from urllib.parse import urlsplit
    try:
        p = urlsplit(u.strip()).path or "/"
    except Exception:
        p = u
    p = p.split("?", 1)[0].split("#", 1)[0].rstrip("/").lower()
    return p or "/"


def _derive_connects_from_visits(nodes: list, visited: list[str]) -> dict[str, list[str]]:
    """
    From the ordered visited-URL sequence, derive observed navigation between
    the discovered nodes. Returns {node_label -> [labels it navigated to]}.
    Consecutive visits whose URLs map to two distinct nodes → an edge.
    """
    # Map normalized path → node label (first node with that path wins).
    label_by_path: dict[str, str] = {}
    for n in nodes:
        p = _normalize_url_path(getattr(n, "url", None))
        if p and p not in label_by_path:
            label_by_path[p] = (getattr(n, "label", None) or "").strip()

    # Walk the visit sequence, mapping each to a node label when possible.
    seq_labels: list[str] = []
    for v in visited:
        lbl = label_by_path.get(_normalize_url_path(v))
        if lbl:
            seq_labels.append(lbl)

    out: dict[str, list[str]] = {}
    for a, b in zip(seq_labels, seq_labels[1:]):
        if a and b and a != b:
            out.setdefault(a, [])
            if b not in out[a]:
                out[a].append(b)
    return out


def _extract_trajectory(history) -> list:
    """
    Build the ordered TrajectoryStep list the relationship engine needs, from a
    browser-use AgentHistoryList. Best-effort and fully defensive: any missing
    field degrades to None and never raises (a failure here must never break the
    explore — we simply derive fewer relationships).

    Evidence per step (verified against browser-use 0.13.7 AgentHistoryList):
      - state.url per step  → the URL the action LANDED on (captures redirects).
      - model_output.action → the action taken; go_to_url carries a target url.
      - interacted_element.ax_name → visible text of the clicked element.
    """
    from .intelligence.relationships import TrajectoryStep

    steps: list = []
    try:
        items = list(getattr(history, "history", []) or [])
    except Exception:
        return steps

    prev_url: Optional[str] = None
    for h in items:
        try:
            state = getattr(h, "state", None)
            url_after = getattr(state, "url", None) if state is not None else None

            action_name = ""
            intended_url: Optional[str] = None
            element_text: Optional[str] = None

            model_output = getattr(h, "model_output", None)
            actions = getattr(model_output, "action", None) if model_output else None
            if actions:
                first = actions[0]
                try:
                    adict = first.model_dump(exclude_none=True, mode="json")
                except Exception:
                    adict = {}
                meta = {"result", "error", "interacted_element", "step"}
                keys = [k for k in adict if k not in meta]
                if keys:
                    action_name = keys[0]
                    params = adict.get(action_name)
                    if isinstance(params, dict):
                        # go_to_url carries the explicit intended target.
                        intended_url = params.get("url") or params.get("href")

            # Visible text of the element the agent interacted with, if any.
            try:
                interacted = getattr(state, "interacted_element", None) if state else None
                if interacted:
                    el = interacted[0] if isinstance(interacted, list) else interacted
                    element_text = getattr(el, "ax_name", None) or getattr(el, "node_value", None)
            except Exception:
                element_text = None

            steps.append(TrajectoryStep(
                url_before=prev_url,
                url_after=url_after,
                action=action_name or "",
                intended_url=intended_url,
                element_text=element_text,
            ))
            if url_after:
                prev_url = url_after
        except Exception:
            # Skip an unparseable step; never abort the whole extraction.
            continue
    return steps


# ---------------------------------------------------------------------------
# The explore task
# ---------------------------------------------------------------------------
@celery_app.task(
    max_retries=1,
    autoretry_for=(),  # do NOT auto-retry exploration; it's expensive
    name="app.explore_worker.explore_application",
)
def explore_application(
    job_id: str,
    application_id: int,
    owner_id: Optional[str],
    base_url: str,
    login_hint: Optional[str] = None,
    max_steps: int = 40,
) -> dict[str, Any]:
    """
    Explore an application and persist its map.

    Lifecycle:
      1. ExploreRun → RUNNING
      2. Build LLM, run an exploration Agent with structured output
      3. Persist discovered nodes to AppMapNode
      4. ExploreRun → COMPLETED / FAILED
    """
    import traceback

    _update_explore_status(
        job_id,
        status=ExploreRunStatus.RUNNING,
        patch={"started_at": datetime.utcnow()},
    )

    try:
        llm = get_llm()
    except Exception as exc:
        _update_explore_status(
            job_id,
            status=ExploreRunStatus.FAILED,
            patch={
                "error_message": f"LLM init failed: {exc}",
                "completed_at": datetime.utcnow(),
            },
        )
        raise RuntimeError(f"LLM init failed: {exc}") from exc

    # ── Build the exploration task prompt ──────────────────────────────────
    task_parts = [
        f"You are mapping the web application at: {base_url}",
        "",
        "GOAL: Systematically explore this application and build a map of its "
        "important pages, forms, and user flows. Navigate like a curious new "
        "user. Click into main navigation links, open key pages, and identify "
        "interactive forms (login, signup, search, checkout, contact, etc.).",
        "",
        "RULES:",
        "1. Do NOT submit forms with real data, do NOT complete purchases, and "
        "do NOT perform destructive actions (delete, cancel, pay). Only OBSERVE.",
        "2. Prefer breadth over depth — visit many distinct areas rather than "
        "going very deep into one.",
        "3. For each important thing you find, record it as a node: a page, a "
        "form, or a multi-step flow (like 'checkout' or 'onboarding').",
        "4. For each node, draft a short natural-language QA test prompt that "
        "would verify it works (e.g. 'Log in with valid credentials and verify "
        "the dashboard loads').",
        "5. For each node, set `business_category` to the ONE best-fitting "
        "business function you actually observed (authentication, billing, "
        "checkout, onboarding, account, navigation, content, search, or other). "
        "Use 'other' when genuinely unsure — never guess.",
        "6. For each node, fill `connects_to` with the exact labels of the OTHER "
        "nodes it navigates to, based on links/buttons you actually saw (e.g. a "
        "'Cart' page with a 'Proceed to checkout' button → connects_to: "
        "['Checkout']). This captures the real navigation structure. Leave it "
        "empty if you observed no outgoing links. Do NOT invent connections.",
        "7. For each node, fill `depends_on` ONLY when you actually HIT A GATE "
        "requiring another node — e.g. a page redirected you to log in "
        "(depends_on: ['Login']), or an action required a precondition you "
        "observed (apply-coupon needed a non-empty cart → depends_on: ['Cart']). "
        "This is the MOST valuable signal: it tells us what breaks if that "
        "dependency breaks. Never guess a dependency you did not encounter.",
        "8. For any multi-step `flow` node, fill `flow_steps` with the ordered "
        "labels of the pages/forms that compose it (e.g. a 'Checkout' flow → "
        "['Cart', 'Shipping', 'Payment']). Use exact labels of nodes in the map.",
        "9. When finished, call done() and return the structured application map.",
    ]
    if login_hint:
        task_parts += [
            "",
            f"LOGIN HINT (use only to access authenticated areas): {login_hint}",
        ]

    # Memory hint (additive, guarded): remind the explorer of auth patterns
    # Leaka already learned for this app. Never fails the explore.
    mem_hint = _explore_memory_hint(application_id, owner_id)
    if mem_hint:
        task_parts += ["", mem_hint]

    task_text = "\n".join(task_parts)

    async def _run_explore():
        from browser_use import Agent
        from browser_use.browser.session import BrowserSession

        browser_session = BrowserSession(headless=True)
        live_step_buffer: list[dict] = []
        visited: list[str] = []

        def _on_step(browser_state_summary, agent_output, step_index: int):
            try:
                entry: dict = {"step": step_index, "action": {}}
                if agent_output and hasattr(agent_output, "action"):
                    actions = agent_output.action
                    if actions:
                        action_dict = actions[0].model_dump(exclude_none=True, mode="json")
                        meta = {"result", "error", "interacted_element", "step"}
                        keys = [k for k in action_dict if k not in meta]
                        if keys:
                            entry["action"] = {keys[0]: action_dict.get(keys[0], {})}
                if browser_state_summary and hasattr(browser_state_summary, "url"):
                    entry["url"] = browser_state_summary.url
                    if browser_state_summary.url and browser_state_summary.url not in visited:
                        visited.append(browser_state_summary.url)
                live_step_buffer.append(entry)

                db = SessionLocal()
                try:
                    run = db.query(ExploreRun).filter(ExploreRun.job_id == job_id).first()
                    if run:
                        run.live_steps = json.dumps(live_step_buffer, default=str)
                        run.visited_urls = json.dumps(visited, ensure_ascii=False)
                        db.commit()
                except Exception:
                    pass
                finally:
                    db.close()
            except Exception:
                pass  # never let the callback break the agent

        agent = Agent(
            task=task_text,
            llm=llm,
            browser_session=browser_session,
            use_vision=True,
            use_thinking=False,
            max_failures=5,
            max_actions_per_step=5,
            step_timeout=60,
            llm_timeout=60,
            message_compaction=False,
            output_model_schema=ApplicationMap,
            register_new_step_callback=_on_step,
        )
        history = await agent.run(max_steps=max_steps)

        # Extract structured output
        app_map: Optional[ApplicationMap] = None
        try:
            structured = history.structured_output
            if isinstance(structured, ApplicationMap):
                app_map = structured
        except Exception:
            app_map = None

        try:
            await browser_session.stop()
        except Exception:
            pass

        return history, app_map, visited

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            history, app_map, visited = loop.run_until_complete(_run_explore())
        finally:
            try:
                loop.run_until_complete(asyncio.sleep(0.1))
            except Exception:
                pass
            loop.close()
            asyncio.set_event_loop(None)
    except Exception as exc:
        tb = traceback.format_exc()
        _update_explore_status(
            job_id,
            status=ExploreRunStatus.FAILED,
            patch={
                "error_message": f"Explore runtime error: {exc}\n{tb}"[:4000],
                "completed_at": datetime.utcnow(),
            },
        )
        raise

    # ── Persist discovered nodes ────────────────────────────────────────────
    nodes = list(app_map.nodes) if app_map else []
    summary = app_map.summary if app_map else None

    # Deterministic navigation fallback: {label -> [labels it navigated to]},
    # derived from the ORDERED visit sequence. Used only where the LLM left
    # connects_to empty.
    derived_connects = _derive_connects_from_visits(nodes, visited or [])

    # Evidence-based relationship derivation (navigates_to / depends_on /
    # part_of_flow) from the OBSERVED trajectory. This is the high-value signal
    # the LLM routinely omits — derived from what the agent demonstrably did,
    # never fabricated. Used ONLY as a fallback (an LLM-provided value wins).
    # Fully guarded: any failure yields empty derivations, never breaks explore.
    derived_depends: dict[str, list[str]] = {}
    derived_flow_steps: dict[str, list[str]] = {}
    derived_nav: dict[str, list[str]] = {}
    try:
        from .intelligence.relationships import RelNode, derive_relationships

        rel_nodes = [
            RelNode(
                label=(n.label or "").strip(),
                url=getattr(n, "url", None),
                node_type=(n.node_type or "page"),
                business_category=(getattr(n, "business_category", None)
                                   or _infer_category(getattr(n, "url", None),
                                                      getattr(n, "label", None))),
            )
            for n in nodes
        ]
        trajectory = _extract_trajectory(history)
        rel = derive_relationships(trajectory, rel_nodes)
        derived_depends = rel.depends_on or {}
        derived_flow_steps = rel.flow_steps or {}
        derived_nav = rel.connects_to or {}
        logger.info(
            "relationship derivation (job_id=%s): +%s navigates_to, +%s depends_on, +%s flows",
            job_id, sum(len(v) for v in derived_nav.values()),
            sum(len(v) for v in derived_depends.values()),
            len(derived_flow_steps),
        )
    except Exception as exc:  # noqa: BLE001 — derivation must never break explore
        logger.warning("Relationship derivation skipped (job_id=%s): %s", job_id, exc)

    db = SessionLocal()
    try:
        run_row = db.query(ExploreRun).filter(ExploreRun.job_id == job_id).first()
        run_pk = run_row.id if run_row else None
        _ALLOWED_CATS = {
            "authentication", "billing", "checkout", "onboarding", "account",
            "navigation", "content", "search", "other",
        }
        for n in nodes[:200]:  # hard cap
            node_type = (n.node_type or "page").strip().lower()
            if node_type not in ("page", "form", "flow"):
                node_type = "page"

            # ── Category: LLM value if given+valid, else inferred from URL/label.
            cat = (getattr(n, "business_category", None) or "").strip().lower() or None
            if cat and cat not in _ALLOWED_CATS:
                cat = "other"
            if not cat:
                cat = _infer_category(getattr(n, "url", None), getattr(n, "label", None))

            # ── Relationship label lists (LLM-provided).
            def _labels(attr: str) -> list[str]:
                vals = getattr(n, attr, None) or []
                return [str(c).strip() for c in vals if str(c).strip()][:20]

            node_label = (n.label or "").strip()

            connects = _labels("connects_to")
            # Fallback (weakest→strongest): if the LLM gave no navigation, prefer
            # the evidence-based trajectory derivation (real actions), then fall
            # back to visit-order adjacency.
            if not connects:
                connects = (
                    derived_nav.get(node_label)
                    or derived_connects.get(node_label, [])
                )[:20]

            # depends_on: the blast-radius signal. LLM value wins; otherwise use
            # the gate-redirect evidence derived from the trajectory.
            depends = _labels("depends_on")
            if not depends:
                depends = derived_depends.get(node_label, [])[:20]

            # flow_steps: LLM value wins; otherwise use the contiguous-flow-run
            # evidence (only emitted for genuinely multi-step business areas).
            steps = _labels("flow_steps")
            if not steps:
                steps = derived_flow_steps.get(node_label, [])[:20]

            db.add(AppMapNode(
                owner_id=owner_id,
                application_id=application_id,
                explore_run_id=run_pk,
                node_type=node_type,
                label=(n.label or "Untitled")[:500],
                url=(n.url or None),
                description=(n.description or None),
                business_category=cat,
                connects_to=(json.dumps(connects) if connects else None),
                depends_on=(json.dumps(depends) if depends else None),
                flow_steps=(json.dumps(steps) if steps else None),
                suggested_prompt=(n.suggested_prompt or None),
            ))
        db.commit()
    finally:
        db.close()

    _update_explore_status(
        job_id,
        status=ExploreRunStatus.COMPLETED,
        patch={
            "nodes_found": len(nodes),
            "result_summary": summary or f"Discovered {len(nodes)} node(s).",
            "visited_urls": json.dumps(visited, ensure_ascii=False),
            "completed_at": datetime.utcnow(),
        },
    )

    # ── Downstream (additive): reconcile discoveries into the Application Graph.
    # This is a NEW, best-effort step. It never alters the explore result above;
    # if dispatch or reconciliation fails, the user still has their map. The
    # graph_worker owns its own transaction, advisory lock, and failure record.
    try:
        if run_pk is not None:
            from .graph_worker import _dispatch_reconcile
            _dispatch_reconcile(run_pk)
    except Exception as exc:  # noqa: BLE001 — reconciliation must not affect explore
        logger.warning("Could not enqueue graph reconciliation (job_id=%s): %s", job_id, exc)

    return {
        "job_id": job_id,
        "status": ExploreRunStatus.COMPLETED.value,
        "nodes_found": len(nodes),
    }
