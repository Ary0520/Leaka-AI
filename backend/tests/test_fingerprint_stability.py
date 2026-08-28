"""
Property 2 — Fingerprint stability (Requirements 1.2).

Design statement:
  "For a fixed discovery, `canonical_key` is invariant across repeated
   computation and across cosmetic text changes that don't alter
   url/structure."

`intelligence/fingerprint.py` is a PURE module (no I/O, no randomness), so
these tests need no database, no network, and no cleanup. They are fast and
fully deterministic — the property is a statement about the function itself.

We validate three facets of stability:
  1. Determinism: computing canonical_key twice for the same discovery yields
     the identical value (Property 2, "repeated computation").
  2. URL-anchored invariance: when a node HAS a URL, its identity is anchored
     to the normalized url_signature + node_type. Cosmetic label/description
     changes (whitespace, case, wording) MUST NOT change canonical_key, and
     id-like path segments (numeric / UUID / long-hex / slug-number) MUST
     normalize so /orders/123 and /orders/456 are one identity.
  3. URL-less fallback: when a node has NO URL, identity falls back to the
     text_signature — so there, a *semantic* label change legitimately DOES
     change identity, but pure whitespace/case normalization does NOT (the
     text signature normalizes case+whitespace before hashing).
"""

from __future__ import annotations

import re

from hypothesis import assume, given, settings, strategies as st

from app.intelligence.fingerprint import (
    Discovery,
    compute_canonical_key,
    compute_fingerprint,
    normalize_url,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
_NODE_TYPES = st.sampled_from(["page", "form", "flow", "action", "role"])

# Arbitrary human text for labels/descriptions (the "cosmetic" content).
_TEXT = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),  # exclude surrogates
    min_size=0,
    max_size=60,
)

# A path segment that is NOT id-like (so normalization leaves it as a lowercased
# slug). We keep it alphabetic to avoid accidentally matching the id patterns.
_PLAIN_SEGMENT = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    min_size=1,
    max_size=10,
)


def _whitespace_variants(text: str) -> list[str]:
    """
    Variants that differ ONLY in whitespace — surrounding and internal.
    fingerprint._normalize_text strips and collapses whitespace before hashing,
    so these MUST hash identically for ANY text (full Unicode).
    """
    return [
        text,
        f"   {text}   ",
        re.sub(r" ", "   ", text),          # expand single spaces to triples
        f"\t{text}\n",
    ]


def _case_variants(text: str) -> list[str]:
    """
    Variants that differ in case. NOTE: `_normalize_text` normalizes via
    `str.lower()`, so the invariant is "lowering is stable". `str.upper()` is
    NOT a lossless cosmetic op for all Unicode (e.g. 'ß'.upper() == 'SS', whose
    lower() is 'ss' ≠ 'ß'), so we only assert case-invariance for inputs whose
    casing round-trips through lower(). Callers restrict the alphabet to ASCII
    letters where this always holds.
    """
    return [text, text.upper(), text.lower()]


# ---------------------------------------------------------------------------
# Facet 1 — Determinism (repeated computation)
# ---------------------------------------------------------------------------
@settings(max_examples=200, deadline=None)
@given(
    node_type=_NODE_TYPES,
    label=_TEXT,
    url=st.one_of(st.none(), st.text(min_size=0, max_size=80)),
    description=st.one_of(st.none(), _TEXT),
)
def test_canonical_key_is_deterministic(node_type, label, url, description):
    """Same discovery in → identical canonical_key every time (no randomness)."""
    d = Discovery(node_type=node_type, label=label, url=url, description=description)
    k1 = compute_canonical_key(d)
    k2 = compute_canonical_key(d)
    assert k1 == k2

    # The full fingerprint is likewise deterministic.
    fp1 = compute_fingerprint(d)
    fp2 = compute_fingerprint(d)
    assert fp1 == fp2


# ---------------------------------------------------------------------------
# Facet 2 — URL-anchored nodes: cosmetic text changes don't move identity
# ---------------------------------------------------------------------------
@settings(max_examples=200, deadline=None)
@given(
    node_type=_NODE_TYPES,
    base_label=_TEXT,
    segments=st.lists(_PLAIN_SEGMENT, min_size=1, max_size=4),
)
def test_url_node_identity_invariant_to_cosmetic_text(node_type, base_label, segments):
    """
    A node WITH a URL is identified by url_signature + node_type. Changing only
    the label/description cosmetically (whitespace/case/wording) must not change
    canonical_key.
    """
    path = "/" + "/".join(segments)
    url = f"https://app.example.com{path}?ref=nav#top"

    reference = Discovery(node_type=node_type, label=base_label, url=url)
    ref_key = compute_canonical_key(reference)

    # When a URL exists, identity is url-anchored — ANY label change (cosmetic
    # or semantic) must not move it. Whitespace + case + full rewording.
    for variant in _whitespace_variants(base_label) + [base_label.upper(), base_label.lower()]:
        d = Discovery(node_type=node_type, label=variant, url=url, description="anything")
        assert compute_canonical_key(d) == ref_key, (
            f"label change moved url-anchored identity: {variant!r}"
        )

    # A completely different label/description also must not matter — identity
    # is url-anchored when a URL exists.
    d2 = Discovery(
        node_type=node_type,
        label=base_label + " (totally reworded wording here)",
        url=url,
        description="an entirely different description",
    )
    assert compute_canonical_key(d2) == ref_key


@settings(max_examples=200, deadline=None)
@given(
    node_type=_NODE_TYPES,
    resource=_PLAIN_SEGMENT,
    id_a=st.integers(min_value=0, max_value=10_000_000),
    id_b=st.integers(min_value=0, max_value=10_000_000),
)
def test_id_like_segments_collapse_to_single_identity(node_type, resource, id_a, id_b):
    """
    Structurally-equivalent URLs that differ only in an id-like path segment
    (/orders/123 vs /orders/456) collapse to the SAME canonical identity.
    """
    d_a = Discovery(node_type=node_type, label="x", url=f"https://s.com/{resource}/{id_a}")
    d_b = Discovery(node_type=node_type, label="y", url=f"https://s.com/{resource}/{id_b}")
    assert compute_canonical_key(d_a) == compute_canonical_key(d_b)


@settings(max_examples=200, deadline=None)
@given(url=st.text(min_size=0, max_size=100))
def test_normalize_url_is_idempotent_and_deterministic(url):
    """normalize_url is a pure normalization: stable and idempotent."""
    once = normalize_url(url)
    twice = normalize_url(url)
    assert once == twice
    # Feeding the already-normalized path back through must be a fixed point.
    assert normalize_url(once) == once


# ---------------------------------------------------------------------------
# Facet 3 — URL-less nodes: identity is the (normalized) text signature
# ---------------------------------------------------------------------------
@settings(max_examples=200, deadline=None)
@given(node_type=_NODE_TYPES, label=st.text(min_size=1, max_size=40))
def test_urlless_node_identity_invariant_to_whitespace(node_type, label):
    """
    A URL-less node (modal/form) falls back to text_signature, which strips +
    collapses whitespace before hashing. So whitespace-only variants keep the
    same canonical_key for ANY (full-Unicode) label, even without a URL anchor.
    """
    # Ensure the label has some non-whitespace content so the text signature is
    # meaningful (an all-whitespace label normalizes to "" — still stable, but
    # not what this facet is about).
    assume(label.strip() != "")

    reference = Discovery(node_type=node_type, label=label, url=None)
    ref_key = compute_canonical_key(reference)

    for variant in _whitespace_variants(label):
        d = Discovery(node_type=node_type, label=variant, url=None)
        assert compute_canonical_key(d) == ref_key, (
            f"whitespace change moved URL-less identity: {variant!r}"
        )


@settings(max_examples=200, deadline=None)
@given(node_type=_NODE_TYPES, label=_PLAIN_SEGMENT)
def test_urlless_node_identity_invariant_to_case_for_ascii(node_type, label):
    """
    For ASCII-letter labels (where casing losslessly round-trips through
    lower()), a URL-less node's identity is invariant to case as well — because
    text_signature lowercases before hashing.
    """
    reference = Discovery(node_type=node_type, label=label, url=None)
    ref_key = compute_canonical_key(reference)

    for variant in _case_variants(label):
        d = Discovery(node_type=node_type, label=variant, url=None)
        assert compute_canonical_key(d) == ref_key, (
            f"case change moved URL-less ASCII identity: {variant!r}"
        )


@settings(max_examples=200, deadline=None)
@given(
    node_type=_NODE_TYPES,
    label=st.text(min_size=1, max_size=40),
    url_path=st.lists(_PLAIN_SEGMENT, min_size=1, max_size=3),
)
def test_empty_url_forms_use_text_fallback_not_url(node_type, label, url_path):
    """
    Explicitly empty/blank URL strings behave like URL-less nodes (text
    fallback), not like a node with a real url_signature.
    """
    assume(label.strip() != "")
    d_blank = Discovery(node_type=node_type, label=label, url="   ")
    d_none = Discovery(node_type=node_type, label=label, url=None)
    # Blank URL normalizes to "" → fingerprint falls back to text identity,
    # identical to the None-url discovery.
    assert compute_canonical_key(d_blank) == compute_canonical_key(d_none)


# ---------------------------------------------------------------------------
# Concrete anchored examples (fast smoke coverage of the property)
# ---------------------------------------------------------------------------
def test_examples_fixed_points():
    # Repeated computation is identical.
    d = Discovery(node_type="page", label="Checkout", url="https://shop.com/checkout")
    assert compute_canonical_key(d) == compute_canonical_key(d)

    # Cosmetic label change, same URL → same identity.
    a = Discovery(node_type="page", label="Checkout", url="https://shop.com/cart")
    b = Discovery(node_type="page", label="  CHECKOUT  page ", url="https://shop.com/cart")
    assert compute_canonical_key(a) == compute_canonical_key(b)

    # id-collapse: /orders/123 == /orders/456.
    o1 = Discovery(node_type="page", label="Order", url="https://shop.com/orders/123?x=1#h")
    o2 = Discovery(node_type="page", label="Order", url="https://shop.com/orders/456")
    assert compute_canonical_key(o1) == compute_canonical_key(o2)

    # node_type is part of identity: same URL, different type → different key.
    p = Discovery(node_type="page", label="Login", url="https://shop.com/login")
    f = Discovery(node_type="form", label="Login", url="https://shop.com/login")
    assert compute_canonical_key(p) != compute_canonical_key(f)

    # URL-less fallback: different wording → different identity (legitimately).
    m1 = Discovery(node_type="form", label="Add coupon", url=None)
    m2 = Discovery(node_type="form", label="Delete account", url=None)
    assert compute_canonical_key(m1) != compute_canonical_key(m2)
