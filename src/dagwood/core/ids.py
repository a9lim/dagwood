"""Short, stable node ids.

Crockford base32 (lowercase, no i/l/o/u) for typability and unambiguous reading.
Ids are random, generated once at creation, never reused or renumbered — git
blame, the layout sidecar, and agent references all key off them.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterable

# Crockford base32 alphabet, lowercased, excluding i l o u.
_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"


def _rand(n: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def new_id(existing: Iterable[str], length: int = 3) -> str:
    """Return a fresh id not in `existing`.

    Starts at `length` chars (3 → 15 bits → 32768 values) and grows by one char
    after every 16 consecutive collisions, so it stays short until the namespace
    is genuinely crowded.
    """
    have = set(existing)
    n = max(1, length)
    tries = 0
    while True:
        candidate = _rand(n)
        if candidate not in have:
            return candidate
        tries += 1
        if tries % 16 == 0:
            n += 1
