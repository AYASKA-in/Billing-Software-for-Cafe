from __future__ import annotations

import base64
import hashlib
import hmac
import os


PIN_HASH_PREFIX = "pbkdf2_sha256"
PIN_HASH_ITERATIONS = 120_000


def hash_pin(pin: str, *, salt: bytes | None = None) -> str:
    clean_pin = str(pin or "")
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        clean_pin.encode("utf-8"),
        salt,
        PIN_HASH_ITERATIONS,
    )
    return "$".join(
        [
            PIN_HASH_PREFIX,
            str(PIN_HASH_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def verify_pin(pin: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False

    try:
        prefix, iterations_raw, salt_raw, digest_raw = stored_hash.split("$", 3)
        if prefix != PIN_HASH_PREFIX:
            return False
        iterations = int(iterations_raw)
        salt = base64.b64decode(salt_raw.encode("ascii"))
        expected = base64.b64decode(digest_raw.encode("ascii"))
    except Exception:
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256",
        str(pin or "").encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)
