"""Notification candidate selection and sender helpers."""

from __future__ import annotations

import json
import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any
from urllib import error, request

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from jobscout_shared.models import Job, JobMatch
from jobscout_shared.settings import Settings


@dataclass(slots=True)
class NotificationCandidate:
    job_id: int
    title: str
    company: str
    url: str
    total_score: float
    decision: str
    fetched_at: datetime


@dataclass(slots=True)
class NotificationBatch:
    top_jobs: list[NotificationCandidate]
    new_high_score_jobs: list[NotificationCandidate]


def _coerce_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def collect_notification_candidates(
    session_factory: sessionmaker[Session],
    top_n: int,
    score_threshold: float,
    lookback_hours: int,
) -> NotificationBatch:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, lookback_hours))

    with session_factory() as session:
        stmt = (
            select(
                Job.id,
                Job.title,
                Job.company,
                Job.url,
                Job.fetched_at,
                JobMatch.total_score,
                JobMatch.decision,
            )
            .join(JobMatch, JobMatch.job_id == Job.id)
            .order_by(JobMatch.total_score.desc(), Job.fetched_at.desc(), Job.id.desc())
        )
        rows = session.execute(stmt).all()

    candidates = [
        NotificationCandidate(
            job_id=row.id,
            title=row.title,
            company=row.company,
            url=row.url,
            total_score=float(row.total_score or 0.0),
            decision=str(row.decision or "review"),
            fetched_at=_coerce_datetime(row.fetched_at),
        )
        for row in rows
    ]

    top_jobs = candidates[: max(1, top_n)]
    new_high_score_jobs = [
        candidate
        for candidate in candidates
        if candidate.total_score >= score_threshold and candidate.fetched_at >= cutoff
    ]

    return NotificationBatch(top_jobs=top_jobs, new_high_score_jobs=new_high_score_jobs)


def _format_jobs_lines(jobs: list[NotificationCandidate]) -> list[str]:
    lines: list[str] = []
    for idx, job in enumerate(jobs, start=1):
        url = job.url if len(job.url) <= 200 else job.url[:200] + "…"
        lines.append(
            f"{idx}. [{job.total_score:.2f}] {job.title} @ {job.company} ({job.decision})\n   {url}"
        )
    return lines


def build_notification_messages(
    batch: NotificationBatch,
    score_threshold: float,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []

    if batch.top_jobs:
        body = "\n".join(
            [
                "Top jobs snapshot:",
                *_format_jobs_lines(batch.top_jobs),
            ]
        )
        messages.append(
            {
                "event": "top_jobs_daily",
                "subject": "JobScout Top Jobs Daily",
                "body": body,
            }
        )

    if batch.new_high_score_jobs:
        body = "\n".join(
            [
                f"New jobs above score threshold ({score_threshold:.2f}):",
                *_format_jobs_lines(batch.new_high_score_jobs),
            ]
        )
        messages.append(
            {
                "event": "new_high_score_jobs",
                "subject": "JobScout New High-Score Jobs",
                "body": body,
            }
        )

    return messages


def send_discord_webhook(webhook_url: str, content: str, timeout_seconds: int = 8) -> tuple[bool, str]:
    payload = json.dumps({"content": content}).encode("utf-8")
    req = request.Request(
        webhook_url,
        data=payload,
        headers={
            "content-type": "application/json",
            "user-agent": "JobScout/0.1 (discord-notifier)",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            status = int(getattr(response, "status", 200))
            if 200 <= status < 300:
                return True, ""
            return False, f"discord webhook responded with status {status}"
    except error.URLError as exc:
        return False, str(exc)


def send_email_notification(
    host: str,
    port: int,
    username: str,
    password: str,
    use_tls: bool,
    sender: str,
    recipients: list[str],
    subject: str,
    body: str,
) -> tuple[bool, str]:
    if not recipients:
        return False, "no recipients configured"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=8) as client:
            if use_tls:
                client.starttls()
            if username:
                client.login(username, password)
            client.send_message(message)
        return True, ""
    except Exception as exc:  # pragma: no cover - network service dependent
        return False, str(exc)


def send_notifications(settings: Settings, messages: list[dict[str, str]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "attempted": len(messages),
        "sent": 0,
        "channels": [],
        "errors": [],
    }
    if not messages:
        return summary

    webhook_url = settings.discord_webhook_url.strip()
    email_to = [item.strip() for item in settings.notification_email_to.split(",") if item.strip()]
    email_from = settings.notification_email_from.strip()

    for message in messages:
        subject = message["subject"]
        body = message["body"]
        event = message["event"]
        any_channel_ok = False

        if webhook_url:
            ok, err = send_discord_webhook(webhook_url, content=body)
            summary["channels"].append({"event": event, "channel": "discord", "ok": ok})
            if ok:
                any_channel_ok = True
            else:
                summary["errors"].append(f"discord:{event}:{err}")

        if settings.smtp_host.strip() and email_to and email_from:
            ok, err = send_email_notification(
                host=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_username,
                password=settings.smtp_password,
                use_tls=settings.smtp_use_tls,
                sender=email_from,
                recipients=email_to,
                subject=subject,
                body=body,
            )
            summary["channels"].append({"event": event, "channel": "email", "ok": ok})
            if ok:
                any_channel_ok = True
            else:
                summary["errors"].append(f"email:{event}:{err}")

        if any_channel_ok:
            summary["sent"] += 1

    return summary
