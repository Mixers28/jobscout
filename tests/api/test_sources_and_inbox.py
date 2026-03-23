from unittest.mock import patch

import httpx
import pytest

pytestmark = pytest.mark.anyio


def _sample_sources() -> list[dict]:
    return [
        {
            "name": "Email Alerts",
            "type": "email_alert",
            "enabled": True,
            "config_json": {
                "company": "AlertCo",
                "location_text": "Aberdeen",
                "messages": [
                    "Subject: M365 Engineer\nDate: Tue, 18 Feb 2026 10:00:00 +0000\n\n"
                    "Role details here https://jobs.example.com/role-1?utm_source=email"
                ],
            },
        },
        {
            "name": "RSS Feed",
            "type": "rss",
            "enabled": True,
            "config_json": {
                "feed_xml": """
                <rss><channel>
                    <item>
                        <title>Infrastructure Engineer</title>
                        <link>https://jobs.example.com/role-2?utm_medium=rss</link>
                        <description>Backup and M365 operations</description>
                        <company>RssCo</company>
                        <location>Inverness</location>
                    </item>
                </channel></rss>
                """,
            },
        },
        {
            "name": "Whitelisted Site",
            "type": "whitelist_career_page",
            "enabled": True,
            "config_json": {
                "allowed_domains": ["careers.safe.example.com"],
                "pages": [
                    {
                        "url": "https://careers.safe.example.com/jobs",
                        "html": (
                            '<a href="/jobs/role-3" data-company="SafeCo" '
                            'data-location="Dundee">Senior IT Support</a>'
                            '<a href="https://evil.example.com/blocked">Blocked</a>'
                        ),
                    }
                ],
            },
        },
    ]


async def test_source_register_ingest_and_dedupe(api_client: httpx.AsyncClient) -> None:
    register_response = await api_client.post("/sources/register", json=_sample_sources())
    assert register_response.status_code == 200
    assert len(register_response.json()) == 3

    ingest_response = await api_client.post("/sources/ingest/run")
    assert ingest_response.status_code == 200
    first_summary = ingest_response.json()
    assert first_summary["sources_processed"] == 3
    assert first_summary["jobs_inserted"] >= 3

    second_ingest = await api_client.post("/sources/ingest/run")
    assert second_ingest.status_code == 200
    second_summary = second_ingest.json()
    assert second_summary["jobs_inserted"] == 0
    assert second_summary["jobs_deduped"] >= first_summary["jobs_inserted"]


async def test_inbox_and_decision_updates(api_client: httpx.AsyncClient) -> None:
    await api_client.post("/sources/register", json=_sample_sources())
    await api_client.post("/sources/ingest/run")
    score_response = await api_client.post("/jobs/score/run", json={"use_embeddings": False})
    assert score_response.status_code == 200
    assert score_response.json()["jobs_scored"] >= 1

    inbox_response = await api_client.get("/jobs/inbox", params={"sort_by": "score"})
    assert inbox_response.status_code == 200
    inbox = inbox_response.json()
    assert len(inbox) >= 1
    assert "total_score" in inbox[0]
    assert "top_reasons" in inbox[0]
    assert "missing_keywords" in inbox[0]

    job_id = inbox[0]["id"]
    explain_response = await api_client.get(f"/jobs/{job_id}/explain")
    assert explain_response.status_code == 200
    explain_payload = explain_response.json()
    assert explain_payload["job_id"] == job_id
    assert "score_breakdown" in explain_payload

    decision_response = await api_client.post(f"/jobs/{job_id}/decision", json={"decision": "apply"})
    assert decision_response.status_code == 200
    assert decision_response.json()["decision"] == "apply"

    pack_response = await api_client.get(f"/jobs/{job_id}/pack")
    assert pack_response.status_code == 200
    assert pack_response.json()["job_id"] == job_id

    apply_only_response = await api_client.get("/jobs/inbox", params={"decision": "apply"})
    assert apply_only_response.status_code == 200
    apply_only = apply_only_response.json()
    assert any(job["id"] == job_id for job in apply_only)


async def test_source_enable_disable_filtering(api_client: httpx.AsyncClient) -> None:
    register_response = await api_client.post("/sources/register", json=_sample_sources())
    source_id = register_response.json()[0]["id"]

    disable_response = await api_client.patch(f"/sources/{source_id}/enabled", json={"enabled": False})
    assert disable_response.status_code == 200
    assert disable_response.json()["enabled"] is False

    enabled_only_response = await api_client.get("/sources", params={"enabled_only": True})
    assert enabled_only_response.status_code == 200
    enabled_sources = enabled_only_response.json()
    assert all(source["id"] != source_id for source in enabled_sources)


async def test_generate_and_fetch_application_pack(api_client: httpx.AsyncClient) -> None:
    await api_client.post("/sources/register", json=_sample_sources())
    await api_client.post("/sources/ingest/run")
    await api_client.post("/jobs/score/run", json={"use_embeddings": False})

    inbox = (await api_client.get("/jobs/inbox", params={"sort_by": "score"})).json()
    job_id = inbox[0]["id"]

    generate_response = await api_client.post(f"/jobs/{job_id}/pack/generate")
    assert generate_response.status_code == 200
    generated = generate_response.json()
    assert generated["job_id"] == job_id
    assert "cv_variant_md" in generated
    assert "cover_letter_md" in generated
    assert isinstance(generated["screening_answers"], list)
    assert isinstance(generated["claims"], list)
    assert isinstance(generated["needs_user_input"], list)
    assert generated["status"] in {"OK", "NEEDS_USER_INPUT"}

    for claim in generated["claims"]:
        assert claim["evidence_refs"]
        assert all(ref["path"] for ref in claim["evidence_refs"])

    fetch_response = await api_client.get(f"/jobs/{job_id}/pack")
    assert fetch_response.status_code == 200
    fetched = fetch_response.json()
    assert fetched["pack_id"] == generated["pack_id"]
    assert fetched["job_id"] == job_id


async def test_tracking_transitions_and_analytics_summary(api_client: httpx.AsyncClient) -> None:
    await api_client.post("/sources/register", json=_sample_sources())
    await api_client.post("/sources/ingest/run")
    await api_client.post("/jobs/score/run", json={"use_embeddings": False})

    inbox = (await api_client.get("/jobs/inbox", params={"sort_by": "score"})).json()
    job_id = inbox[0]["id"]

    first_update = await api_client.patch(
        f"/jobs/{job_id}/tracking",
        json={"stage": "applied", "outcome": "pending"},
    )
    assert first_update.status_code == 200
    assert first_update.json()["stage"] == "applied"
    assert first_update.json()["applied_at"] is not None

    second_update = await api_client.patch(
        f"/jobs/{job_id}/tracking",
        json={"stage": "closed", "outcome": "callback"},
    )
    assert second_update.status_code == 200
    assert second_update.json()["outcome"] == "callback"

    invalid_transition = await api_client.patch(
        f"/jobs/{job_id}/tracking",
        json={"stage": "applied"},
    )
    assert invalid_transition.status_code == 400

    analytics_response = await api_client.get("/jobs/analytics/summary")
    assert analytics_response.status_code == 200
    analytics = analytics_response.json()
    assert analytics["total_jobs"] >= 1
    assert analytics["applied_jobs"] >= 1
    assert analytics["callback_jobs"] >= 1
    assert isinstance(analytics["source_conversion_rates"], list)


async def test_schedule_run_and_run_logs(api_client: httpx.AsyncClient) -> None:
    await api_client.post("/sources/register", json=_sample_sources())
    run_response = await api_client.post("/jobs/schedule/run")
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["status"] in {"success", "failed"}
    assert "run_id" in run_payload
    assert "attempts" in run_payload

    runs_response = await api_client.get("/jobs/schedule/runs")
    assert runs_response.status_code == 200
    runs = runs_response.json()
    assert len(runs) >= 1
    assert runs[0]["status"] in {"success", "failed"}


async def test_decision_rollback_on_pack_failure(api_client: httpx.AsyncClient) -> None:
    """When pack generation fails, update_decision should rollback the decision and return 500."""
    await api_client.post("/sources/register", json=_sample_sources())
    await api_client.post("/sources/ingest/run")
    await api_client.post("/jobs/score/run", json={"use_embeddings": False})

    inbox = (await api_client.get("/jobs/inbox", params={"sort_by": "score"})).json()
    job_id = inbox[0]["id"]

    # Confirm initial decision is not "apply".
    initial_decision = inbox[0]["decision"]
    assert initial_decision != "apply"

    with patch(
        "app.routers.jobs.run_pack_generation",
        side_effect=RuntimeError("simulated pack failure"),
    ):
        response = await api_client.post(f"/jobs/{job_id}/decision", json={"decision": "apply"})

    assert response.status_code == 500
    assert "pack generation failed" in response.json().get("detail", "")

    # Verify the decision was rolled back.
    explain = (await api_client.get(f"/jobs/{job_id}/explain")).json()
    assert explain["decision"] != "apply"


async def test_invalid_source_url_rejected(api_client: httpx.AsyncClient) -> None:
    """SourceDefinition with a non-http URL should be rejected at registration."""
    bad_sources = [
        {
            "name": "Bad RSS",
            "type": "rss",
            "enabled": True,
            "config_json": {"feed_url": "file:///etc/passwd"},
        }
    ]
    response = await api_client.post("/sources/register", json=bad_sources)
    assert response.status_code == 422


async def test_decision_update_unknown_job_returns_404(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post("/jobs/99999/decision", json={"decision": "apply"})
    assert response.status_code == 404


async def test_tracking_update_invalid_transition_returns_400(api_client: httpx.AsyncClient) -> None:
    await api_client.post("/sources/register", json=_sample_sources())
    await api_client.post("/sources/ingest/run")
    inbox = (await api_client.get("/jobs/inbox")).json()
    job_id = inbox[0]["id"]

    # "new" -> "offer" is not a valid transition.
    response = await api_client.patch(f"/jobs/{job_id}/tracking", json={"stage": "offer"})
    assert response.status_code == 400
