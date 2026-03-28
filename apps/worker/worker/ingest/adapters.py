"""Ingestion adapters for email alerts, RSS feeds, and whitelisted pages."""

from __future__ import annotations

import imaplib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from email import message_from_bytes, message_from_string
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any, cast
from urllib import error, request
from urllib.parse import urljoin, urlsplit, urlparse
from xml.etree import ElementTree

from jobscout_shared.normalization import normalize_whitespace
from jobscout_shared.schemas import NormalizedJob


URL_RE = re.compile(r"https?://[^\s<>)\]]+")

_log = logging.getLogger(__name__)


@dataclass(slots=True)
class AdapterOutput:
    jobs: list[NormalizedJob]
    seen: int
    fetched_uids: list[str] = field(default_factory=list)


class AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._active: dict[str, str] | None = None
        self._text_parts: list[str] = []
        self.anchors: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr_map = {k: (v or "") for k, v in attrs}
        href = attr_map.get("href", "")
        if not href:
            return
        self._active = attr_map
        self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._active is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._active is None:
            return
        text = normalize_whitespace(" ".join(self._text_parts))
        anchor = dict(self._active)
        anchor["text"] = text
        self.anchors.append(anchor)
        self._active = None
        self._text_parts = []


def _safe_datetime(raw_value: str | None) -> datetime | None:
    if not raw_value:
        return None
    try:
        return parsedate_to_datetime(raw_value)
    except (TypeError, ValueError):
        return None


_MAX_FETCH_BYTES = 5 * 1024 * 1024  # 5 MB guard against oversized responses


def _fetch_url_text(url: str, timeout_seconds: int = 10) -> tuple[str, str]:
    """Fetch a URL and return (page_text, final_url_after_redirects).

    Returns ("", original_url) on any error.
    """
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "", url
    req = request.Request(
        url,
        headers={
            "user-agent": "Mozilla/5.0 (compatible; JobScout/0.1; +ingest)",
        },
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            final_url = response.url or url
            payload = response.read(_MAX_FETCH_BYTES)
            content_type = response.headers.get("content-type", "")
            charset = "utf-8"
            if "charset=" in content_type:
                charset = content_type.split("charset=", maxsplit=1)[-1].split(";", maxsplit=1)[0].strip()
            return payload.decode(charset or "utf-8", errors="ignore"), final_url
    except (error.URLError, ValueError, OSError):
        return "", url


def _extract_email_body(raw_message: str) -> str:
    message = message_from_string(raw_message)
    if message.is_multipart():
        parts: list[str] = []
        for part in message.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if isinstance(payload, (bytes, bytearray)):
                    parts.append(payload.decode(errors="ignore"))
        return normalize_whitespace("\n".join(parts))
    payload = message.get_payload(decode=True)
    if not isinstance(payload, (bytes, bytearray)):
        text_payload = message.get_payload()
        return normalize_whitespace(str(text_payload))
    return normalize_whitespace(payload.decode(errors="ignore"))


def fetch_imap_messages(config: dict) -> tuple[list[str], list[str]]:
    """Connect to an IMAP server and return (raw_messages, uid_strings) for unseen mail.

    Credentials are read from *config* first; any key absent in config falls back to
    the global Settings instance so a single mailbox can serve multiple sources.
    All errors are caught and logged — the function always returns empty lists on failure
    so the ingest pipeline degrades gracefully.
    """
    # Lazily import settings to avoid a circular-import at module load time.
    from jobscout_shared.settings import get_settings  # noqa: PLC0415

    settings = get_settings()

    host = str(config.get("imap_host", "") or settings.imap_host).strip()
    port = int(config.get("imap_port", 0) or settings.imap_port)
    username = str(config.get("imap_username", "") or settings.imap_username).strip()
    password = str(config.get("imap_password", "") or settings.imap_password).strip()
    use_ssl = bool(config.get("imap_use_ssl", settings.imap_use_ssl))
    mailbox = str(config.get("imap_mailbox", "") or settings.imap_mailbox).strip() or "INBOX"
    max_fetch = int(config.get("imap_max_fetch", 0) or settings.imap_max_fetch)

    if not host or not username or not password:
        return [], []

    already_seen: set[str] = {str(uid) for uid in config.get("seen_uids", [])}

    try:
        client: imaplib.IMAP4
        if use_ssl:
            client = imaplib.IMAP4_SSL(host, port)
        else:
            client = imaplib.IMAP4(host, port)

        with client:
            client.login(username, password)
            status, _ = client.select(mailbox, readonly=True)
            if status != "OK":
                _log.warning("IMAP: could not select mailbox %r on %s", mailbox, host)
                return [], []

            # Search for all unseen messages.
            status, data = client.uid("search", cast(Any, None), "UNSEEN")
            if status != "OK" or not data or not data[0]:
                return [], []

            all_uids: list[str] = data[0].decode().split()
            # Exclude UIDs we have already processed in a previous ingest cycle.
            new_uids = [uid for uid in all_uids if uid not in already_seen]
            # Respect the per-cycle fetch cap.
            uids_to_fetch = new_uids[:max_fetch]

            if not uids_to_fetch:
                return [], []

            uid_set = ",".join(uids_to_fetch)
            status, fetch_data = client.uid("fetch", uid_set, "(RFC822)")
            if status != "OK" or not fetch_data:
                return [], []

            raw_messages: list[str] = []
            fetched_uids: list[str] = []
            for i, item in enumerate(fetch_data):
                if not isinstance(item, tuple):
                    continue
                raw_bytes = item[1]
                if not isinstance(raw_bytes, (bytes, bytearray)):
                    continue
                raw_messages.append(message_from_bytes(raw_bytes).as_string())
                # Pair each message body with its UID from the ordered list.
                if i // 2 < len(uids_to_fetch):
                    fetched_uids.append(uids_to_fetch[i // 2])

        _log.info("IMAP: fetched %d new messages from %s/%s", len(raw_messages), host, mailbox)
        return raw_messages, fetched_uids

    except (imaplib.IMAP4.error, OSError, ValueError) as exc:
        _log.warning("IMAP fetch failed for %s: %s", host, exc)
        return [], []


# Sender domains/addresses whose mail is never job-related (Google account housekeeping etc.)
_SYSTEM_SENDER_BLOCKLIST = frozenset([
    "no-reply@accounts.google.com",
    "no-reply@google.com",
    "noreply@google.com",
    "mail-noreply@google.com",
    "no-reply@mail.google.com",
])

_SYSTEM_SUBJECT_FRAGMENTS = (
    "security alert",
    "2-step verification",
    "finish setting up your new google account",
    "gmail forwarding confirmation",
    "sign-in attempt",
)


def _is_system_email(message_from_string_result: object) -> bool:
    """Return True if the email is a provider system/housekeeping message, not a job alert."""
    from_header = str(getattr(message_from_string_result, "get", lambda k, d="": d)("From", "")).lower()
    subject = str(getattr(message_from_string_result, "get", lambda k, d="": d)("Subject", "")).lower()
    if any(addr in from_header for addr in _SYSTEM_SENDER_BLOCKLIST):
        return True
    if any(fragment in subject for fragment in _SYSTEM_SUBJECT_FRAGMENTS):
        return True
    return False


# Anchor link text that indicates a footer/nav link, not a job listing.
_EMAIL_NAV_LINK_TEXTS = frozenset([
    "view all jobs", "view all", "edit your job alert", "edit alert",
    "manage your contact preferences", "unsubscribe", "privacy policy",
    "terms and conditions", "sign in", "jobs", "courses", "career advice",
    "rate this job alert", "view job", "apply now", "reed.co.uk",
    "indeed", "adzuna", "totaljobs", "cwjobs",
    # Indeed email section headers that get picked up as anchor text
    "since yesterday", "for last 7 days", "for last 14 days", "for last 30 days",
    "edit this job alert", "delete this job alert", "view all matches",
    "see all jobs", "more jobs", "show more", "see more jobs",
    # Adzuna nav/promo links
    "value my cv now", "value my cv", "applyiq", "apply iq",
    "get hired on the go", "get the app",
])

# URL substrings that indicate tracking/footer links rather than job pages.
_EMAIL_NAV_URL_FRAGMENTS = (
    "/alerts/cancel", "/my-alerts", "/unsubscribe", "/legal",
    "/hc/en", "support.", "subscriptions.indeed.com?", "/imgping",
    "fonts.gstatic", "fonts.googleapis",
    "/opt_out_alert", "/value-my-cv", "/in-your-inbox",
    "/privacy-policy", "/terms-and-conditions", "/jobs/search",
    # Indeed redirect/tracking links that don't resolve to job pages
    "e.jm.indeed.com", "engage.indeed.com", "subscriptions.indeed.com",
    "indeed.com/rc/clk", "indeed.com/pagead/clk",
    # Adzuna promo/non-job URLs
    "/jobs/apply-iq", "adzuna.co.uk/jobs/value-my-cv",
)

# Substrings in fetched page content that indicate the page is not a real job listing.
_BAD_PAGE_CONTENT_MARKERS = (
    "google has many special features",
    "search the world's information",
    "enable javascript",
    "please enable cookies",
    "access denied",
    "indeed job alerts email",  # got redirected back to email template
)


def _extract_html_part(raw_message: str) -> str:
    """Return the text/html part of an email, or empty string."""
    message = message_from_string(raw_message)
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if isinstance(payload, (bytes, bytearray)):
                    return payload.decode(errors="ignore")
    payload = message.get_payload(decode=True)
    if isinstance(payload, (bytes, bytearray)):
        return payload.decode(errors="ignore")
    return ""


def _parse_job_listings_from_html(html: str) -> list[tuple[str, str]]:
    """Return a deduplicated list of (title, url) pairs from a job alert HTML email.

    The strategy is:
    1. Parse all anchor tags via AnchorParser.
    2. Keep only anchors whose link text looks like a job title (non-empty, not a
       known nav phrase, not too long) and whose URL is not a known footer URL.
    3. Deduplicate by URL, keeping the first title seen for each URL.
    """
    parser = AnchorParser()
    parser.feed(html)

    seen_urls: dict[str, str] = {}  # url -> title

    for anchor in parser.anchors:
        href = normalize_whitespace(anchor.get("href", ""))
        text = normalize_whitespace(anchor.get("text", ""))

        if not href or not text:
            continue
        if not href.startswith("http"):
            continue

        # Skip nav/footer URLs.
        if any(frag in href for frag in _EMAIL_NAV_URL_FRAGMENTS):
            continue

        # Skip nav/footer link texts.
        if text.lower().replace("\xa0", " ") in _EMAIL_NAV_LINK_TEXTS:
            continue

        # Skip very short texts (single words like "here", "click") and very long ones.
        if len(text) < 4 or len(text) > 120:
            continue

        # Skip texts that are just a domain name or plain URL.
        if text.startswith("http") or "." in text and " " not in text:
            continue

        if href not in seen_urls:
            seen_urls[href] = text

    return [(title, url) for url, title in seen_urls.items()]


def parse_email_alert_jobs(source_name: str, config_json: dict) -> AdapterOutput:
    # Fetch live messages from IMAP if credentials are configured.
    imap_host = str(config_json.get("imap_host", "")).strip()
    fetched_uids: list[str] = []
    if imap_host:
        live_messages, fetched_uids = fetch_imap_messages(config_json)
    else:
        # Fall back to checking global settings.
        from jobscout_shared.settings import get_settings  # noqa: PLC0415
        if get_settings().imap_host.strip():
            live_messages, fetched_uids = fetch_imap_messages(config_json)
        else:
            live_messages = []

    # Combine live IMAP messages with any statically stored messages (paste-in).
    messages: list[str] = live_messages + list(config_json.get("messages", []))

    fallback_company = config_json.get("company", source_name)
    fallback_location = config_json.get("location_text", "")
    fetch_pages = bool(config_json.get("fetch_job_pages", True))
    seen = 0
    jobs: list[NormalizedJob] = []

    for raw_message in messages:
        seen += 1
        message = message_from_string(raw_message)

        # Skip Google account housekeeping and other non-job system emails.
        if _is_system_email(message):
            _log.debug("Skipping system email: %s", message.get("Subject", ""))
            continue

        posted_at = _safe_datetime(message.get("Date"))
        html = _extract_html_part(raw_message)

        # Try to extract individual (title, url) job listing pairs from HTML.
        listings: list[tuple[str, str]] = []
        if html:
            listings = _parse_job_listings_from_html(html)

        # Fall back to plain-text URL extraction if HTML parsing found nothing.
        if not listings:
            body = _extract_email_body(raw_message)
            subject = normalize_whitespace(message.get("Subject", "Job alert"))
            urls = URL_RE.findall(body)
            for url in urls:
                if not any(frag in url for frag in _EMAIL_NAV_URL_FRAGMENTS):
                    listings.append((subject, url))

        for title, url in listings:
            # Optionally fetch the job page to get a real description for scoring.
            description = ""
            canonical_url = url
            if fetch_pages:
                page_html, canonical_url = _fetch_url_text(url)
                if page_html:
                    page_text = normalize_whitespace(re.sub(r"<[^>]+>", " ", page_html))
                    # Discard pages that are clearly not job listings (redirected to
                    # Google, error pages, or back to the email template itself).
                    page_lower = page_text.lower()
                    if not any(marker in page_lower for marker in _BAD_PAGE_CONTENT_MARKERS):
                        description = page_text
                    else:
                        # Bad redirect — revert to original tracking URL
                        canonical_url = url

            if not description:
                # Fall back to the email body so scoring has something to work with.
                description = normalize_whitespace(
                    re.sub(r"<[^>]+>", " ", html) if html else _extract_email_body(raw_message)
                )

            jobs.append(
                NormalizedJob(
                    title=title,
                    company=fallback_company,
                    location_text=fallback_location,
                    url=canonical_url,
                    description_text=description,
                    requirements_text=None,
                    posted_at=posted_at,
                )
            )

    return AdapterOutput(jobs=jobs, seen=seen, fetched_uids=fetched_uids)


def parse_rss_jobs(source_name: str, config_json: dict) -> AdapterOutput:
    feed_xml = str(config_json.get("feed_xml", "")).strip()
    if not feed_xml:
        feed_url = normalize_whitespace(str(config_json.get("feed_url", "")))
        if feed_url:
            feed_xml, _ = _fetch_url_text(feed_url)

    if not feed_xml:
        return AdapterOutput(jobs=[], seen=0)

    try:
        root = ElementTree.fromstring(feed_xml)
    except ElementTree.ParseError:
        return AdapterOutput(jobs=[], seen=0)
    jobs: list[NormalizedJob] = []
    seen = 0

    for item in root.findall("./channel/item"):
        seen += 1
        title = normalize_whitespace(item.findtext("title", default="RSS Job"))
        link = normalize_whitespace(item.findtext("link", default=""))
        description = normalize_whitespace(item.findtext("description", default=""))
        company = normalize_whitespace(item.findtext("company", default=source_name))
        location = normalize_whitespace(item.findtext("location", default=""))

        if not link:
            continue

        jobs.append(
            NormalizedJob(
                title=title,
                company=company or source_name,
                location_text=location,
                url=link,
                description_text=description or title,
                posted_at=_safe_datetime(item.findtext("pubDate")),
            )
        )

    return AdapterOutput(jobs=jobs, seen=seen)


def parse_whitelist_page_jobs(source_name: str, config_json: dict) -> AdapterOutput:
    raw_pages: list[dict] = config_json.get("pages", [])
    page_urls = [
        normalize_whitespace(str(item))
        for item in config_json.get("page_urls", [])
        if normalize_whitespace(str(item))
    ]
    pages: list[dict] = [*raw_pages, *({"url": url} for url in page_urls)]
    allowed_domains = {domain.lower() for domain in config_json.get("allowed_domains", [])}
    fallback_company = config_json.get("company", source_name)
    seen = 0
    jobs: list[NormalizedJob] = []

    for page in pages:
        seen += 1
        page_url = normalize_whitespace(page.get("url", ""))
        html = str(page.get("html", ""))
        if not page_url:
            continue

        if not html:
            html, _ = _fetch_url_text(page_url)

        if not html:
            continue

        parser = AnchorParser()
        parser.feed(html)

        for anchor in parser.anchors:
            href = normalize_whitespace(anchor.get("href", ""))
            if not href:
                continue

            absolute_url = urljoin(page_url, href)
            domain = (urlsplit(absolute_url).netloc or "").lower()
            if allowed_domains and domain not in allowed_domains:
                continue

            title = normalize_whitespace(anchor.get("text", "")) or "Whitelisted Job"
            company = normalize_whitespace(anchor.get("data-company", "")) or fallback_company
            location = normalize_whitespace(anchor.get("data-location", ""))

            jobs.append(
                NormalizedJob(
                    title=title,
                    company=company,
                    location_text=location,
                    url=absolute_url,
                    description_text=normalize_whitespace(html),
                )
            )

    return AdapterOutput(jobs=jobs, seen=seen)
