"""
Supabase JWT authentication for FastAPI.

New Supabase projects (2025+) use asymmetric ES256 signing via JWKS.
We fetch the public keys from the JWKS endpoint once, cache them in-process,
and verify every incoming Bearer token locally — no network round-trip per request.

Verified against:
  https://objectgraph.com/blog/migrating-supabase-jwt-jwks/
  https://supabase.com/docs/guides/auth/jwts
"""

import logging
import threading
from typing import Any, Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt

from .config import settings

logger = logging.getLogger("revguard.auth")

_bearer = HTTPBearer(auto_error=False)

# ── JWKS cache ────────────────────────────────────────────────────────────────
_jwks_cache: Optional[dict[str, Any]] = None
_jwks_lock = threading.Lock()


def _get_jwks() -> dict[str, Any]:
    """Fetch JWKS from Supabase and cache in-process (thread-safe)."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    url = settings.SUPABASE_JWKS_URL
    if not url:
        raise RuntimeError("SUPABASE_JWKS_URL is not configured in .env")

    with _jwks_lock:
        if _jwks_cache is not None:          # double-check after lock
            return _jwks_cache
        try:
            resp = httpx.get(url, timeout=10)
            resp.raise_for_status()
            _jwks_cache = resp.json()
            logger.info("JWKS fetched and cached from %s", url)
        except Exception as exc:
            logger.error("Failed to fetch JWKS: %s", exc)
            raise RuntimeError(f"Could not fetch Supabase JWKS: {exc}") from exc

    return _jwks_cache


def _get_signing_key(kid: str) -> str:
    """Find the public key matching `kid` in the cached JWKS and return PEM."""
    jwks_data = _get_jwks()
    for key in jwks_data.get("keys", []):
        if key.get("kid") == kid:
            return jwk.construct(key).to_pem().decode()
    # Key not found — might be a rotation; bust cache and retry once
    global _jwks_cache
    _jwks_cache = None
    jwks_data = _get_jwks()
    for key in jwks_data.get("keys", []):
        if key.get("kid") == kid:
            return jwk.construct(key).to_pem().decode()
    raise ValueError(f"No JWKS key found for kid={kid!r}")


def verify_token(token: str) -> dict[str, Any]:
    """
    Verify a Supabase JWT and return its claims.
    Supports ES256 (asymmetric, default for new projects) and HS256 (legacy).
    """
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token") from exc

    alg = header.get("alg", "ES256")

    try:
        if alg == "ES256":
            kid = header.get("kid")
            if not kid:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token missing kid")
            signing_key = _get_signing_key(kid)
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=["ES256"],
                options={"verify_aud": False},
            )
        else:
            # HS256 fallback — uses the project JWT secret (older projects)
            # If you ever need this path, set SUPABASE_JWT_SECRET in .env
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "HS256 tokens not supported — enable asymmetric signing in Supabase",
            )
    except JWTError as exc:
        logger.warning("JWT verification failed: %s", exc)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc

    return payload


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict[str, Any]:
    """
    FastAPI dependency — extracts and verifies the Supabase Bearer token.
    Returns the JWT payload (contains `sub` = user UUID, `email`, `role`, etc.).
    Raises 401 if token is missing or invalid.
    """
    if not creds or not creds.credentials:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Authentication required. Please sign in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_token(creds.credentials)


def get_current_user_optional(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[dict[str, Any]]:
    """
    Like get_current_user but returns None instead of raising for unauthenticated requests.
    Used for endpoints that are public but show more data when authed.
    """
    if not creds or not creds.credentials:
        return None
    try:
        return verify_token(creds.credentials)
    except HTTPException:
        return None
