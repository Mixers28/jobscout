from worker.ingest import adapters
from worker.ingest.adapters import (
    parse_email_alert_jobs,
    parse_rss_jobs,
    parse_whitelist_page_jobs,
)


def test_email_adapter_parses_alert_links() -> None:
    output = parse_email_alert_jobs(
        "Email Alerts",
        {
            "company": "AlertCo",
            "messages": [
                "Subject: M365 Engineer\nDate: Tue, 18 Feb 2026 10:00:00 +0000\n\n"
                "Apply here https://jobs.example.com/role-1"
            ],
        },
    )

    assert output.seen == 1
    assert len(output.jobs) == 1
    assert output.jobs[0].title == "M365 Engineer"


def test_rss_adapter_parses_items() -> None:
    output = parse_rss_jobs(
        "RSS Feed",
        {
            "feed_xml": """
            <rss><channel>
                <item>
                    <title>Infrastructure Engineer</title>
                    <link>https://jobs.example.com/role-2</link>
                    <description>Backup and operations</description>
                    <company>RssCo</company>
                    <location>Inverness</location>
                </item>
            </channel></rss>
            """,
        },
    )

    assert output.seen == 1
    assert len(output.jobs) == 1
    assert output.jobs[0].company == "RssCo"


def test_rss_adapter_fetches_feed_from_url(monkeypatch) -> None:
    feed_xml = """
    <rss><channel>
        <item>
            <title>Systems Administrator</title>
            <link>https://jobs.example.com/role-4</link>
            <description>M365 and backup support</description>
            <company>FeedCo</company>
            <location>Aberdeen</location>
        </item>
    </channel></rss>
    """
    monkeypatch.setattr(
        adapters,
        "_fetch_url_text",
        lambda _url: (feed_xml, "https://feeds.example.com/jobs.xml"),
    )

    output = parse_rss_jobs(
        "RSS Feed",
        {
            "feed_url": "https://feeds.example.com/jobs.xml",
        },
    )

    assert output.seen == 1
    assert len(output.jobs) == 1
    assert output.jobs[0].title == "Systems Administrator"


def test_whitelist_adapter_enforces_allowed_domains() -> None:
    output = parse_whitelist_page_jobs(
        "Whitelist",
        {
            "allowed_domains": ["careers.safe.example.com"],
            "pages": [
                {
                    "url": "https://careers.safe.example.com/jobs",
                    "html": (
                        '<a href="/jobs/role-3" data-company="SafeCo" data-location="Dundee">'
                        "Senior IT Support</a>"
                        '<a href="https://evil.example.com/blocked">Blocked</a>'
                    ),
                }
            ],
        },
    )

    assert output.seen == 1
    assert len(output.jobs) == 1
    assert output.jobs[0].company == "SafeCo"
    assert "careers.safe.example.com" in output.jobs[0].url


def test_whitelist_adapter_fetches_page_urls(monkeypatch) -> None:
    html = (
        '<a href="/jobs/role-5" data-company="SiteCo" data-location="Inverness">'
        "Infrastructure Engineer</a>"
    )
    monkeypatch.setattr(
        adapters,
        "_fetch_url_text",
        lambda _url: (html, "https://careers.safe.example.com/jobs"),
    )

    output = parse_whitelist_page_jobs(
        "Whitelist",
        {
            "allowed_domains": ["careers.safe.example.com"],
            "page_urls": ["https://careers.safe.example.com/jobs"],
        },
    )

    assert output.seen == 1
    assert len(output.jobs) == 1
    assert output.jobs[0].title == "Infrastructure Engineer"
    assert output.jobs[0].company == "SiteCo"


def test_email_adapter_skips_links_that_resolve_to_non_job_pages(monkeypatch) -> None:
    monkeypatch.setattr(
        adapters,
        "_fetch_url_text",
        lambda _url: (
            "Google Search the world's information, including webpages, images, videos and more.",
            "https://www.google.com/",
        ),
    )

    output = parse_email_alert_jobs(
        "Email Alerts",
        {
            "company": "AlertCo",
            "messages": [
                "Subject: Service Desk Analyst\nDate: Tue, 18 Feb 2026 10:00:00 +0000\n\n"
                "Apply here https://example.com/tracking/job-1"
            ],
        },
    )

    assert output.seen == 1
    assert output.jobs == []
