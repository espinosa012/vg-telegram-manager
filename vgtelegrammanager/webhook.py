"""
HMAC signing of webhook requests.

When a ``webhook_secret`` is configured, every POST to ``process_messages_endpoint``
carries two headers:

- ``X-VGTM-Timestamp``: Unix time (seconds) at which the request was signed.
- ``X-VGTM-Signature``: ``sha256=<hex>`` HMAC-SHA256 of ``"<timestamp>.<raw body>"``.

Receivers should recompute the signature over the raw request body and reject
requests whose timestamp is too old, e.g. with :func:`verify_webhook_signature`.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Optional

TIMESTAMP_HEADER = "X-VGTM-Timestamp"
SIGNATURE_HEADER = "X-VGTM-Signature"
DEFAULT_TOLERANCE_SECONDS = 300


def _digest(secret: str, timestamp: str, body: bytes) -> str:
    message = timestamp.encode() + b"." + body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def sign_webhook_body(
    secret: str, body: bytes, timestamp: Optional[int] = None
) -> dict[str, str]:
    """Returns the signature headers for a webhook request body."""
    ts = str(int(time.time()) if timestamp is None else timestamp)
    return {TIMESTAMP_HEADER: ts, SIGNATURE_HEADER: f"sha256={_digest(secret, ts, body)}"}


def verify_webhook_signature(
    secret: str,
    body: bytes,
    timestamp: str,
    signature: str,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
) -> bool:
    """
    Verifies a webhook request on the receiving side.

    Args:
        secret: The shared ``webhook_secret``.
        body: The raw request body, exactly as received.
        timestamp: Value of the ``X-VGTM-Timestamp`` header.
        signature: Value of the ``X-VGTM-Signature`` header.
        tolerance_seconds: Maximum accepted age of the request, to limit replays.
    """
    try:
        age = abs(time.time() - int(timestamp))
    except (TypeError, ValueError):
        return False
    if age > tolerance_seconds:
        return False
    expected = f"sha256={_digest(secret, timestamp, body)}"
    return hmac.compare_digest(expected, signature)
