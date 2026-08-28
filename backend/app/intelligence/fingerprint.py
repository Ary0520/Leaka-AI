"""
Node fingerprint computation — the stable identity layer of the Application
Graph (Requirements 1.2, 2.5).

A "discovery" is one thing the explorer found (in our system, an `AppMapNode`:
node_type, label, url, description). From a discovery we compute deterministic
SIGNATURES and a CANONICAL KEY that let us re-identify the same entity across
explore runs even when cosmetic details change.

Everything here is a PURE FUNCTION (no I/O, no randomness) so it is directly
unit- and property-testable and satisfies fingerprint-stability (Property 2).

Signature inventory (per design 1.2):
  - url_signature  : normalized URL (strip scheme/host/query/fragment, collapse
                     numeric & UUID path segments to ':id'). PRIMARY identity.
  - text_signature : hash of normalized label (+ key text). Secondary identity,
                     and the primary signal for URL-less nodes (modals/forms).
  - dom_signature  : hash of salient DOM structure IF present in the discovery.
  - aria_signature : hash of ARIA roles/landmarks IF present in the discovery.

Note on honesty: the current explorer captures url/label/description/node_type
but not raw DOM/ARIA. So dom/aria signatures are computed only when that
evidence is actually provided; otherwise they are None. We never fabricate
signals we don't have.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlsplit


# ---------------------------------------------------------------------------
# Small deterministic helpers
# ---------------------------------------------------------------------------
def _sha16(s: str) -> str:
    """Deterministic short hash (16 hex chars) of a normalized string."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_HEXLONG_RE = re.compile(r"^[0-9a-fA-F]{12,}$")   # long hex ids
_NUMERIC_RE = re.compile(r"^\d+$")


def _normalize_segment(seg: str) -> str:
    """Collapse an id-like path segment to ':id' so /orders/123 == /orders/456."""
    if not seg:
        return seg
    if _NUMERIC_RE.match(seg) or _UUID_RE.match(seg) or _HEXLONG_RE.match(seg):
        return ":id"
    # slug that ends in a number chunk, e.g. product-12345 → product-:id
    m = re.match(r"^(.*?)[-_]?(\d{3,})$", seg)
    if m and m.group(1):
        return f"{m.group(1)}-:id"
    return seg.lower()


def normalize_url(url: Optional[str]) -> str:
    """
    Produce a stable URL signature:
      - drop scheme + host (identity is about the path within an app),
      - drop query string and fragment,
      - lowercase, collapse id-like path segments to ':id',
      - normalize trailing slash.
    Returns "" for empty/None input.

    Examples:
      https://shop.com/orders/123?x=1#top  -> /orders/:id
      https://shop.com/Cart/                -> /cart
      (none)                                -> ""
    """
    if not url or not url.strip():
        return ""
    raw = url.strip()
    try:
        parts = urlsplit(raw)
        path = parts.path or ""
        # If there was no scheme/host, urlsplit puts everything in .path already.
    except Exception:
        path = raw

    # Strip query/fragment defensively even if urlsplit didn't
    path = path.split("?", 1)[0].split("#", 1)[0]

    if not path:
        return "/"
    segments = [s for s in path.split("/") if s != ""]
    norm = "/".join(_normalize_segment(s) for s in segments)
    return "/" + norm if norm else "/"


def _normalize_text(t: Optional[str]) -> str:
    """Lowercase, collapse whitespace — for text signatures."""
    if not t:
        return ""
    return re.sub(r"\s+", " ", t.strip().lower())


# ---------------------------------------------------------------------------
# Discovery + Fingerprint containers (plain, ORM-free)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Discovery:
    """A single explored entity, normalized to a plain structure."""
    node_type: str
    label: str
    url: Optional[str] = None
    description: Optional[str] = None
    dom: Optional[str] = None          # raw salient DOM, if the explorer captured it
    aria: Optional[str] = None         # raw ARIA roles/landmarks, if captured

    @staticmethod
    def from_app_map_node(n: Any) -> "Discovery":
        """Build a Discovery from an ORM AppMapNode (or any object with those attrs)."""
        return Discovery(
            node_type=(getattr(n, "node_type", None) or "page"),
            label=(getattr(n, "label", None) or ""),
            url=getattr(n, "url", None),
            description=getattr(n, "description", None),
            dom=getattr(n, "dom", None),
            aria=getattr(n, "aria", None),
        )


@dataclass(frozen=True)
class Fingerprint:
    url_signature: str
    text_signature: str
    dom_signature: Optional[str]
    aria_signature: Optional[str]


# ---------------------------------------------------------------------------
# Fingerprint + canonical key
# ---------------------------------------------------------------------------
def compute_fingerprint(discovery: Discovery) -> Fingerprint:
    """Compute all deterministic signatures for a discovery."""
    url_sig = normalize_url(discovery.url)
    text_sig = _sha16(_normalize_text(discovery.label))
    dom_sig = _sha16(_normalize_text(discovery.dom)) if discovery.dom else None
    aria_sig = _sha16(_normalize_text(discovery.aria)) if discovery.aria else None
    return Fingerprint(
        url_signature=url_sig,
        text_signature=text_sig,
        dom_signature=dom_sig,
        aria_signature=aria_sig,
    )


def compute_canonical_key(discovery: Discovery) -> str:
    """
    The stable identity of a node within its application.

    Rule (design 1.2):
      - PRIMARY: node_type + normalized url_signature (when a URL exists).
        So the same page keeps one identity regardless of query params / ids.
      - FALLBACK (URL-less nodes like modals/forms): node_type + text_signature.

    Deterministic: same discovery → same key, always (Property 2).
    """
    fp = compute_fingerprint(discovery)
    node_type = (discovery.node_type or "page").strip().lower()

    if fp.url_signature:
        basis = f"{node_type}|url|{fp.url_signature}"
    else:
        # No URL — identity falls back to the (stable) text signature.
        basis = f"{node_type}|text|{fp.text_signature}"

    return _sha16(basis)


# ---------------------------------------------------------------------------
# Identity match score (discovery vs an existing node's stored signatures)
# ---------------------------------------------------------------------------
# Weights sum to 1.0. url dominates; the rest break ties / handle URL-less nodes.
_W_URL = 0.60
_W_TEXT = 0.20
_W_DOM = 0.12
_W_ARIA = 0.08

MATCH_THRESHOLD = 0.72  # >= this ⇒ treat as the same node


@dataclass(frozen=True)
class NodeSignatures:
    """The signatures stored for an existing graph node (its latest fingerprint)."""
    node_type: str
    url_signature: str
    text_signature: str
    dom_signature: Optional[str] = None
    aria_signature: Optional[str] = None


def identity_match_score(discovery: Discovery, node: NodeSignatures) -> float:
    """
    Weighted similarity in [0.0, 1.0] between a discovery and an existing node.

    - Different node_type ⇒ hard 0.0 (a page is never the same entity as a form).
    - url: exact normalized match contributes its full weight.
    - text/dom/aria: exact signature match contributes weight; mismatch/absent = 0.
      Signatures absent on BOTH sides are treated as neutral (do not penalize).
    """
    d_type = (discovery.node_type or "page").strip().lower()
    n_type = (node.node_type or "page").strip().lower()
    if d_type != n_type:
        return 0.0

    fp = compute_fingerprint(discovery)

    score = 0.0
    total_weight = 0.0

    # URL signal
    if fp.url_signature or node.url_signature:
        total_weight += _W_URL
        if fp.url_signature and fp.url_signature == node.url_signature:
            score += _W_URL

    # Text signal (always present — label)
    total_weight += _W_TEXT
    if fp.text_signature == node.text_signature:
        score += _W_TEXT

    # DOM signal (only if either side has it)
    if fp.dom_signature or node.dom_signature:
        total_weight += _W_DOM
        if fp.dom_signature and fp.dom_signature == node.dom_signature:
            score += _W_DOM

    # ARIA signal (only if either side has it)
    if fp.aria_signature or node.aria_signature:
        total_weight += _W_ARIA
        if fp.aria_signature and fp.aria_signature == node.aria_signature:
            score += _W_ARIA

    if total_weight == 0.0:
        return 0.0
    # Normalize so the score is comparable regardless of which signals were present.
    return round(score / total_weight, 6)
