"""PII redaction layer used before any user data is sent to an external LLM.

Why this exists
---------------
Sending raw user data (phone, email, PAN, Aadhaar, IP, account numbers) to
a third-party API is a privacy/compliance risk we refuse to take.  Every
tool output and every prompt that includes user data MUST go through
``redact``/``redact_dict`` first.

What we redact (Indian fintech context)
---------------------------------------
* Mobile numbers           -> ``<PHONE>``
* Emails                   -> ``<EMAIL>``
* PAN cards                -> ``<PAN>``
* Aadhaar numbers          -> ``<AADHAAR>``
* IPv4 addresses           -> ``<IP>``
* Bank account / card-like -> ``<ACCOUNT>``  (long numeric IDs)

Limitations
-----------
This is a regex layer, not full ML-grade DLP.  It is the *last* line of
defence; we still avoid passing data we don't strictly need.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------- #
# Patterns
# ---------------------------------------------------------------------------- #
_PHONE_RE = re.compile(r"(?:\+?91[\s\-]?)?[6-9]\d{9}")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_AADHAAR_RE = re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
# Account/card-like: long contiguous numeric runs (9-19 digits).  We match
# AFTER PAN/Aadhaar/phone so those branches consume their own digits first.
_ACCOUNT_RE = re.compile(r"\b\d{9,19}\b")

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_AADHAAR_RE, "<AADHAAR>"),  # check 12-digit Aadhaar before generic account
    (_PAN_RE, "<PAN>"),
    (_EMAIL_RE, "<EMAIL>"),
    (_PHONE_RE, "<PHONE>"),
    (_IPV4_RE, "<IP>"),
    (_ACCOUNT_RE, "<ACCOUNT>"),
)


def redact(text: str) -> str:
    """Redact PII patterns from a string.  Returns the input unchanged if not str."""
    if not isinstance(text, str) or not text:
        return text
    out = text
    for pattern, replacement in _PATTERNS:
        out = pattern.sub(replacement, out)
    return out


def redact_dict(payload: Any) -> Any:
    """Recursively redact all string values in a dict / list structure.

    Non-string scalars (int, float, bool, None) pass through unchanged so
    risk scores, IDs, and timestamps remain useful for the LLM.
    """
    if isinstance(payload, dict):
        return {k: redact_dict(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [redact_dict(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(redact_dict(item) for item in payload)
    if isinstance(payload, str):
        return redact(payload)
    return payload
