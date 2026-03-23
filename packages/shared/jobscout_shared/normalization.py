"""Normalization helpers for ingestion and deduplication."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"gclid", "fbclid", "mc_cid", "mc_eid"}


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def canonicalize_url(url: str) -> str:
    parts = urlsplit((url or "").strip())
    safe_pairs = []
    for key, val in parse_qsl(parts.query, keep_blank_values=True):
        lower = key.lower()
        if lower in TRACKING_QUERY_KEYS:
            continue
        if lower.startswith(TRACKING_QUERY_PREFIXES):
            continue
        safe_pairs.append((key, val))

    safe_pairs.sort(key=lambda pair: pair[0].lower())
    query = urlencode(safe_pairs, doseq=True)
    canonical_parts = (
        parts.scheme.lower(),
        parts.netloc.lower(),
        parts.path,
        query,
        "",
    )
    return urlunsplit(canonical_parts)


def compute_description_hash(description_text: str) -> str:
    normalized = normalize_whitespace(description_text).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
