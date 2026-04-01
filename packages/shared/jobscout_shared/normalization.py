"""Normalization helpers for ingestion and deduplication."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {
    "alid",
    "c",
    "co",
    "deep_link_value",
    "et",
    "fbclid",
    "fr",
    "from",
    "fromage",
    "gclid",
    "i",
    "mc_cid",
    "mc_eid",
    "nid",
    "rec",
    "se",
    "sl",
    "t",
    "tmtk",
    "token",
    "v",
}

_ADZUNA_DETAILS_PATH_RE = re.compile(r"^/jobs/details/(\d+)/?$")
_REED_JOB_PATH_RE = re.compile(r"^/jobs(?:/[^/]+)*/(\d+)/?$")


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


def _normalize_identity_text(value: str) -> str:
    return normalize_whitespace(value).lower()


def _normalize_host(netloc: str) -> str:
    host = (netloc or "").strip().lower()
    if host.startswith("www."):
        return host[4:]
    return host


def extract_stable_listing_id(url: str) -> str:
    """Return a stable cross-alert listing id when the job board exposes one."""
    parts = urlsplit(canonicalize_url(url))
    host = _normalize_host(parts.netloc)
    path = parts.path or "/"
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    query_map = {key.lower(): value for key, value in query_pairs}

    if host.endswith("adzuna.co.uk") or host.endswith("adzuna.com"):
        match = _ADZUNA_DETAILS_PATH_RE.match(path)
        if match:
            return f"adzuna:{match.group(1)}"

    if host.endswith("reed.co.uk"):
        match = _REED_JOB_PATH_RE.match(path)
        if match:
            return f"reed:{match.group(1)}"

    if "indeed." in host:
        job_key = _normalize_identity_text(query_map.get("jk", ""))
        if job_key:
            return f"indeed:{job_key}"

    return ""


def compute_job_identity(url: str, title: str = "", company: str = "") -> str:
    """Return a stable listing identity for dedupe and notification grouping."""
    stable_listing_id = extract_stable_listing_id(url)
    if stable_listing_id:
        return stable_listing_id

    canonical_url = canonicalize_url(url)
    normalized_title = _normalize_identity_text(title)
    normalized_company = _normalize_identity_text(company)
    if normalized_title or normalized_company:
        return f"{canonical_url}|{normalized_title}|{normalized_company}"
    return canonical_url


def compute_description_hash(description_text: str) -> str:
    normalized = normalize_whitespace(description_text).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
