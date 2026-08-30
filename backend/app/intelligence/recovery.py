"""
Recovery Intelligence — Self-Healing Engine (Application Intelligence).

This engine provides semantic fallback logic when traditional UI interaction fails.
If a UI element changes its ID, class, or text label cosmetically, this model
takes the agent's intent, retrieves historical data for that intent from Memory,
embeds the current live DOM interactive elements, and finds the highest cosine
similarity match to heal the locator.

Design contracts:
  - Pure computation where possible. I/O is passed in or wrapped defensively.
  - Fail-safe: Any failure returns None and never raises, so the agent can 
    gracefully decide its next move.
"""

from __future__ import annotations

import logging
from typing import Optional, Any

import numpy as np

from . import embeddings as EMB
from ..database import SessionLocal
from .. import memory as MEM

logger = logging.getLogger("revguard.intelligence.recovery")


def find_new_locator(
    intent: str,
    application_id: int,
    owner_id: Optional[str],
    live_elements: list[dict[str, str]],
    node_id: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    """
    Find a new working locator for a missing element using semantic similarity.

    Args:
        intent: The natural language intent or description (e.g., "Submit Order").
        application_id: Scopes the memory lookup.
        owner_id: Tenant isolation.
        live_elements: A list of dicts representing interactive elements currently 
                       on the page. Must contain 'xpath', 'text', and optionally 'role'.
        node_id: Optional graph node to narrow the memory search.

    Returns:
        A dict with the best matched element's info (e.g., {"xpath": "...", "confidence": 0.85})
        or None if no confident match is found.
    """
    if not live_elements or not intent.strip():
        return None

    db = SessionLocal()
    try:
        # 1. Retrieve the historical memory of this element to understand what it *used* to look like.
        # We query for 'locator' memories that match the agent's current intent.
        mem_items = MEM.retrieve(
            db, 
            application_id=application_id, 
            owner_id=owner_id, 
            node_id=node_id, 
            kind="locator", 
            query=intent, 
            k=1
        )
        if not mem_items:
            logger.info("Recovery failed: no past locators found for intent '%s'", intent)
            return None
            
        historical = mem_items[0]
        # Memory writes embed_text based on element_text + selector. 
        # Fallback to payload properties if embed_text is lost.
        hist_payload = historical.payload or {}
        historical_text = hist_payload.get("element_text") or hist_payload.get("selector") or intent
        
        # We need the vector representation of the historical element context
        embedder = EMB.get_embedder()
        
        # 2. Extract text representations from the live elements
        live_texts = []
        for el in live_elements:
            text_val = (el.get("text") or "").strip()
            role_val = (el.get("role") or "").strip()
            # Combine role and text to give the embedder semantic context (e.g. "button Submit")
            repr_str = f"{role_val} {text_val}".strip()
            if not repr_str:
                repr_str = el.get("xpath", "")
            live_texts.append(repr_str)
            
        # 3. Embed the historical target and the current live candidates
        # embed() raises EmbeddingUnavailable on failure, caught gracefully below.
        hist_vec = embedder.embed([historical_text])[0]
        live_vecs = embedder.embed(live_texts)
        
        if not hist_vec or not live_vecs:
            return None
            
        # 4. Cosine similarity
        # Normalized embeddings -> cosine similarity is just the dot product.
        h_arr = np.array(hist_vec)
        l_arr = np.array(live_vecs)
        
        # Ensure normalization just in case
        h_norm = np.linalg.norm(h_arr)
        if h_norm == 0: return None
        h_arr = h_arr / h_norm
        
        l_norms = np.linalg.norm(l_arr, axis=1, keepdims=True)
        # Avoid division by zero
        l_norms[l_norms == 0] = 1 
        l_arr = l_arr / l_norms
        
        similarities = np.dot(l_arr, h_arr)
        
        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])
        
        # 5. Confidence check (Threshold can be tuned; 0.60 is generally a safe semantic match for all-MiniLM)
        # OpenAI text-embedding-3 cosine scores run higher, ~0.4+ for loose matches.
        # We'll use 0.45 as a conservative baseline for both.
        if best_score < 0.45:
            logger.info("Recovery failed: best match for '%s' had low confidence (%.2f)", intent, best_score)
            return None
            
        best_element = live_elements[best_idx]
        return {
            "xpath": best_element.get("xpath"),
            "text": best_element.get("text"),
            "confidence": round(best_score, 3),
            "historical_text_matched": historical_text
        }

    except EMB.EmbeddingUnavailable as exc:
        logger.info("Recovery aborted: embeddings unavailable (%s)", exc)
        return None
    except Exception as exc:
        logger.warning("Recovery aborted: unexpected error (%s)", exc)
        return None
    finally:
        db.close()
