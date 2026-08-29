"""
Secret store — encrypt-at-rest secret references for PR Intelligence
(Requirement 9.3: secrets are stored as references, never plaintext, and are
never returned by any read API or shipped to the browser).

Design:
  A "secret ref" is an OPAQUE, encrypted-at-rest token of the form
      enc:v1:<fernet-ciphertext>
  It is what gets persisted in RepoConnection.secret_ref / webhook_secret_ref.
  The plaintext token/secret is NEVER stored in a column and NEVER returned by
  any API. Only server-side callers (the GitHub client, webhook verification)
  call `resolve_secret_ref(...)` to decrypt it in-memory for a single use.

Key management:
  Encryption uses Fernet (AES-128-CBC + HMAC) from the `cryptography` package
  (already a dependency via python-jose[cryptography]). The key comes from the
  `SECRET_STORE_KEY` env var (a urlsafe-base64 32-byte Fernet key). If unset, a
  key is DERIVED deterministically from the app's environment for local/dev use
  and a loud warning is logged — production MUST set SECRET_STORE_KEY.

This module has no DB dependency: the ciphertext lives inline in the ref, so no
extra table/migration is needed and the secret is portable with its row.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("revguard.secrets")

_REF_PREFIX = "enc:v1:"
_MASK = "••••••••"

# Process-cached Fernet instance.
_fernet: Fernet | None = None
_fernet_key_src: str | None = None


def _derive_dev_key() -> bytes:
    """
    Deterministically derive a Fernet key for local/dev when SECRET_STORE_KEY is
    unset. NOT for production — logs a warning. Derived from a fixed app salt +
    DATABASE_URL so it is stable across restarts on the same machine.
    """
    from .config import settings
    seed = f"leaka-secret-store::{settings.DATABASE_URL}".encode("utf-8")
    digest = hashlib.sha256(seed).digest()  # 32 bytes
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    global _fernet, _fernet_key_src
    key_env = os.getenv("SECRET_STORE_KEY")
    src = key_env or "__dev_derived__"
    if _fernet is not None and _fernet_key_src == src:
        return _fernet

    if key_env:
        try:
            key = key_env.encode("utf-8")
            fernet = Fernet(key)  # validates the key
        except Exception as exc:
            raise RuntimeError(
                "SECRET_STORE_KEY is not a valid Fernet key (urlsafe base64, 32 bytes). "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            ) from exc
    else:
        logger.warning(
            "SECRET_STORE_KEY is not set — using a machine-derived dev key. "
            "Set SECRET_STORE_KEY in production so secrets are portable and secure."
        )
        fernet = Fernet(_derive_dev_key())

    _fernet = fernet
    _fernet_key_src = src
    return fernet


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def store_secret(plaintext: str) -> str:
    """
    Encrypt `plaintext` and return an opaque secret ref ("enc:v1:<ciphertext>").
    The ref is what callers persist; the plaintext is never stored elsewhere.
    """
    if plaintext is None:
        raise ValueError("cannot store a None secret")
    token = _get_fernet().encrypt(plaintext.encode("utf-8"))
    return _REF_PREFIX + token.decode("utf-8")


def resolve_secret_ref(ref: str | None) -> str | None:
    """
    Decrypt an opaque secret ref back to plaintext for a single server-side use.
    Returns None if the ref is missing/malformed/undecryptable. NEVER expose the
    return value through an API.
    """
    if not ref or not ref.startswith(_REF_PREFIX):
        return None
    ciphertext = ref[len(_REF_PREFIX):].encode("utf-8")
    try:
        return _get_fernet().decrypt(ciphertext).decode("utf-8")
    except (InvalidToken, Exception):  # noqa: BLE001 — never leak crypto errors
        logger.warning("Failed to resolve a secret ref (key rotated or corrupt ref).")
        return None


def is_ref(value: str | None) -> bool:
    """True if `value` looks like one of our encrypted secret refs (not plaintext)."""
    return bool(value) and value.startswith(_REF_PREFIX)


def mask() -> str:
    """A constant mask string for API responses that must indicate 'a secret is set'."""
    return _MASK
