"""
Deterministic assertion evaluator — the Test Oracle.

This module verifies machine-checkable assertions against the ACTUAL captured
page state (final DOM + final URL) after an agent run completes. It is fully
deterministic and does NOT involve the LLM — this is what makes a test result
trustworthy rather than "the agent said it passed".

Design contract:
  - Assertions can only TIGHTEN correctness. If an assertion fails, the run
    fails. If there are no assertions, this module is never consulted and the
    run behaves exactly as before (LLM verdict only).
  - Evaluation reuses data already captured by the worker (dom_html, urls) —
    no new browser calls, no perf cost.
  - Every result records the outcome and a short human-readable detail.

Supported assertion types (v1):
  - page_contains_text      : visible page text contains `value`
  - page_not_contains_text  : visible page text does NOT contain `value`
  - url_contains            : final URL contains `value`
  - url_equals              : final URL equals `value` (trailing slash tolerant)
  - page_contains_regex     : visible page text matches regex `value`
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, Optional


# ---------------------------------------------------------------------------
# HTML → visible text
# ---------------------------------------------------------------------------
class _TextExtractor(HTMLParser):
    """Collect visible text, skipping <script>/<style> content."""

    _SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "head"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag.lower() in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._chunks.append(text)

    def get_text(self) -> str:
        return " ".join(self._chunks)


def extract_visible_text(dom_html: Optional[str]) -> str:
    """Strip tags/scripts/styles from raw HTML and return visible text."""
    if not dom_html:
        return ""
    try:
        parser = _TextExtractor()
        parser.feed(dom_html)
        return parser.get_text()
    except Exception:
        # Fallback: crude tag strip
        return re.sub(r"<[^>]+>", " ", dom_html)


# ---------------------------------------------------------------------------
# Single assertion evaluation
# ---------------------------------------------------------------------------
def _normalize_url(u: str) -> str:
    return (u or "").strip().rstrip("/").lower()


def evaluate_assertion(
    assertion: dict[str, Any],
    *,
    visible_text: str,
    final_url: Optional[str],
) -> dict[str, Any]:
    """
    Evaluate a single assertion. Returns:
        {"type", "value", "passed": bool, "detail": str}
    Never raises — a malformed assertion is reported as failed with a detail.
    """
    a_type = str(assertion.get("type", "")).strip()
    value = str(assertion.get("value", ""))
    case_sensitive = bool(assertion.get("case_sensitive", False))

    result: dict[str, Any] = {"type": a_type, "value": value, "passed": False, "detail": ""}

    if not a_type or not value:
        result["detail"] = "Malformed assertion (missing type or value)."
        return result

    hay_text = visible_text if case_sensitive else visible_text.lower()
    needle = value if case_sensitive else value.lower()
    url = final_url or ""
    url_cmp = url if case_sensitive else url.lower()

    try:
        if a_type == "page_contains_text":
            passed = needle in hay_text
            result["passed"] = passed
            result["detail"] = (
                f"Found '{value}' on the page." if passed
                else f"'{value}' was NOT found in the page text."
            )

        elif a_type == "page_not_contains_text":
            passed = needle not in hay_text
            result["passed"] = passed
            result["detail"] = (
                f"'{value}' is correctly absent from the page." if passed
                else f"'{value}' was found on the page but should NOT be present."
            )

        elif a_type == "url_contains":
            passed = (needle in url_cmp)
            result["passed"] = passed
            result["detail"] = (
                f"Final URL contains '{value}'." if passed
                else f"Final URL '{url}' does not contain '{value}'."
            )

        elif a_type == "url_equals":
            passed = _normalize_url(url) == _normalize_url(value)
            result["passed"] = passed
            result["detail"] = (
                f"Final URL matches '{value}'." if passed
                else f"Final URL '{url}' does not equal '{value}'."
            )

        elif a_type == "page_contains_regex":
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                passed = re.search(value, visible_text, flags) is not None
            except re.error as rex:
                result["detail"] = f"Invalid regex: {rex}"
                return result
            result["passed"] = passed
            result["detail"] = (
                f"Page text matches pattern /{value}/." if passed
                else f"Page text does not match pattern /{value}/."
            )

        else:
            result["detail"] = f"Unknown assertion type '{a_type}'."

    except Exception as exc:  # never let an assertion crash the run
        result["detail"] = f"Assertion evaluation error: {exc}"

    return result


# ---------------------------------------------------------------------------
# Evaluate all assertions
# ---------------------------------------------------------------------------
def evaluate_assertions(
    assertions: list[dict[str, Any]],
    *,
    dom_html: Optional[str],
    final_url: Optional[str],
) -> tuple[bool, list[dict[str, Any]]]:
    """
    Evaluate a list of assertions against captured page state.

    Returns (all_passed, results). If the list is empty, returns (True, []).
    `all_passed` is True only if EVERY assertion passed.
    """
    if not assertions:
        return True, []

    visible_text = extract_visible_text(dom_html)
    results: list[dict[str, Any]] = []
    all_passed = True

    for a in assertions:
        r = evaluate_assertion(a, visible_text=visible_text, final_url=final_url)
        results.append(r)
        if not r["passed"]:
            all_passed = False

    return all_passed, results
