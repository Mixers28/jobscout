import { fetchFromApi } from "../lib/api";

type Source = {
  id: number;
  name: string;
  type: "email_alert" | "rss" | "whitelist_career_page";
  enabled: boolean;
  config_json: Record<string, unknown>;
};

type SchedulerRun = {
  run_id: string;
  status: "success" | "failed";
  attempts: number;
  started_at: string;
  completed_at: string;
  error: string | null;
};

const ADVANCED_SOURCES_JSON = `[
  {
    "name": "NHS Scotland RSS",
    "type": "rss",
    "enabled": true,
    "config_json": {
      "feed_url": "https://example.com/jobs/feed.xml"
    }
  },
  {
    "name": "Employer Careers Page",
    "type": "whitelist_career_page",
    "enabled": true,
    "config_json": {
      "company": "Example Employer",
      "allowed_domains": ["careers.example.com"],
      "page_urls": ["https://careers.example.com/jobs"]
    }
  }
]`;

async function getSources(): Promise<Source[]> {
  try {
    const response = await fetchFromApi("/sources", { cache: "no-store" });
    if (!response.ok) {
      return [];
    }
    return (await response.json()) as Source[];
  } catch {
    return [];
  }
}

async function getRuns(): Promise<SchedulerRun[]> {
  try {
    const response = await fetchFromApi("/jobs/schedule/runs?limit=10", {
      cache: "no-store",
    });
    if (!response.ok) {
      return [];
    }
    return (await response.json()) as SchedulerRun[];
  } catch {
    return [];
  }
}

export default async function OpsPage() {
  const [sources, runs] = await Promise.all([getSources(), getRuns()]);
  return (
    <main style={{ maxWidth: "980px", margin: "0 auto", padding: "24px" }}>
      <h1>JobScout Ops Console</h1>
      <p>Register sources and run ingest/score/schedule directly from this page.</p>
      <p>
        <a href="/">Back to dashboard</a>
      </p>

      <section style={{ border: "1px solid #ccc", borderRadius: "8px", padding: "16px", marginBottom: "20px" }}>
        <h2>1) Quick Add Website Source</h2>
        <p>Recommended for employer careers pages. Add one URL and we fetch listings from that site.</p>
        <form action="/api/sources/register-site" method="post">
          <div style={{ display: "grid", gap: "8px" }}>
            <label>
              source name
              <br />
              <input
                name="source_name"
                required
                defaultValue="Employer Careers"
                style={{ width: "100%", maxWidth: "440px" }}
              />
            </label>
            <label>
              careers page URL
              <br />
              <input
                name="page_url"
                type="url"
                required
                placeholder="https://careers.example.com/jobs"
                style={{ width: "100%", maxWidth: "640px" }}
              />
            </label>
            <label>
              allowed domain (optional, defaults from URL)
              <br />
              <input name="allowed_domain" placeholder="careers.example.com" style={{ width: "100%", maxWidth: "440px" }} />
            </label>
            <label>
              display company (optional)
              <br />
              <input name="company" placeholder="Example Employer" style={{ width: "100%", maxWidth: "440px" }} />
            </label>
            <label>
              <input type="checkbox" name="enabled" defaultChecked /> enabled
            </label>
          </div>
          <div style={{ marginTop: "10px" }}>
            <button type="submit">add website source</button>
          </div>
        </form>
      </section>

      <section style={{ border: "1px solid #ccc", borderRadius: "8px", padding: "16px", marginBottom: "20px" }}>
        <h2>2) Quick Add RSS Source</h2>
        <p>Use this for job feed URLs. We pull items directly from the feed URL.</p>
        <form action="/api/sources/register-rss" method="post">
          <div style={{ display: "grid", gap: "8px" }}>
            <label>
              source name
              <br />
              <input name="source_name" required defaultValue="RSS Feed" style={{ width: "100%", maxWidth: "440px" }} />
            </label>
            <label>
              feed URL
              <br />
              <input
                name="feed_url"
                type="url"
                required
                placeholder="https://example.com/jobs/feed.xml"
                style={{ width: "100%", maxWidth: "640px" }}
              />
            </label>
            <label>
              display company (optional)
              <br />
              <input name="company" placeholder="Feed Publisher" style={{ width: "100%", maxWidth: "440px" }} />
            </label>
            <label>
              <input type="checkbox" name="enabled" defaultChecked /> enabled
            </label>
          </div>
          <div style={{ marginTop: "10px" }}>
            <button type="submit">add rss source</button>
          </div>
        </form>
      </section>

      <section style={{ border: "1px solid #ccc", borderRadius: "8px", padding: "16px", marginBottom: "20px" }}>
        <h2>3) Quick Add Email Alert</h2>
        <p>
          Got a job-alert email from Reed, Adzuna, LinkedIn, or any recruiter? Paste the full email text below
          (including Subject/Date headers if available) and we will register it as an <code>email_alert</code> source
          so the ingest pipeline can extract the listings on the next run.
        </p>
        <form action="/api/sources/register-email" method="post">
          <div style={{ display: "grid", gap: "8px" }}>
            <label>
              source name <span style={{ color: "#888", fontSize: "0.85em" }}>(unique label for this alert sender)</span>
              <br />
              <input
                name="source_name"
                required
                placeholder="Reed Alert – M365 Aberdeen"
                style={{ width: "100%", maxWidth: "440px" }}
              />
            </label>
            <label>
              company / sender <span style={{ color: "#888", fontSize: "0.85em" }}>(optional)</span>
              <br />
              <input name="company" placeholder="Reed" style={{ width: "100%", maxWidth: "440px" }} />
            </label>
            <label>
              location hint <span style={{ color: "#888", fontSize: "0.85em" }}>(optional – helps score geo-relevance)</span>
              <br />
              <input name="location_text" placeholder="Aberdeen, Scotland" style={{ width: "100%", maxWidth: "440px" }} />
            </label>
            <label>
              email body <span style={{ color: "#888", fontSize: "0.85em" }}>(paste the full email text or HTML here)</span>
              <br />
              <textarea
                name="email_body"
                required
                rows={14}
                placeholder={"Subject: New jobs matching your search: Microsoft 365 Engineer\nDate: Thu, 20 Feb 2026 08:00:00 +0000\n\nHi Michael,\n\nHere are your latest job matches:\n\n1. M365 Administrator – Acme Ltd, Aberdeen\n   £48,000 – £54,000 | Hybrid\n   Apply: https://www.reed.co.uk/jobs/...\n\n..."}
                style={{ width: "100%", fontFamily: "monospace", fontSize: "12px", resize: "vertical" }}
              />
            </label>
            <label>
              <input type="checkbox" name="enabled" defaultChecked /> enabled
            </label>
          </div>
          <div style={{ marginTop: "10px" }}>
            <button type="submit">register email alert source</button>
          </div>
        </form>
      </section>

      <section style={{ border: "1px solid #ccc", borderRadius: "8px", padding: "16px", marginBottom: "20px" }}>
        <h2>4) Auto-Scan Gmail / IMAP Mailbox</h2>
        <p>
          Connect a dedicated Gmail mailbox so JobScout fetches new job-alert emails automatically on every ingest run —
          no manual pasting needed.
        </p>
        <details style={{ marginBottom: "12px", background: "#f9f9f9", padding: "10px", borderRadius: "6px" }}>
          <summary style={{ cursor: "pointer", fontWeight: "bold" }}>How to set up Gmail (click to expand)</summary>
          <ol style={{ marginTop: "8px", lineHeight: "1.7" }}>
            <li>
              Create a free Google account just for job alerts, e.g.{" "}
              <code>yourname.jobscout@gmail.com</code>.
            </li>
            <li>
              Sign in to that account → <strong>Google Account → Security → 2-Step Verification</strong> → turn on.
            </li>
            <li>
              Still in Security → search <strong>App Passwords</strong> → create one named "JobScout" → copy the 16-character
              password (no spaces).
            </li>
            <li>
              Subscribe to job alerts on{" "}
              <a href="https://www.reed.co.uk/jobs/microsoft-365-jobs-in-aberdeen" target="_blank" rel="noreferrer">
                Reed
              </a>
              ,{" "}
              <a href="https://www.adzuna.co.uk" target="_blank" rel="noreferrer">
                Adzuna
              </a>
              , LinkedIn, etc. using that Gmail address as the notification email.
            </li>
            <li>Fill in the form below and click <strong>register IMAP source</strong>.</li>
            <li>
              JobScout will poll <code>INBOX</code> for unseen messages every ingest cycle and skip messages it has
              already processed.
            </li>
          </ol>
        </details>
        <form action="/api/sources/register-imap" method="post">
          <div style={{ display: "grid", gap: "8px" }}>
            <label>
              source name <span style={{ color: "#888", fontSize: "0.85em" }}>(unique label)</span>
              <br />
              <input
                name="source_name"
                required
                placeholder="Gmail Job Alerts"
                style={{ width: "100%", maxWidth: "440px" }}
              />
            </label>
            <label>
              Gmail address <span style={{ color: "#888", fontSize: "0.85em" }}>(the dedicated mailbox)</span>
              <br />
              <input
                name="imap_username"
                type="email"
                required
                placeholder="yourname.jobscout@gmail.com"
                style={{ width: "100%", maxWidth: "440px" }}
              />
            </label>
            <label>
              App Password <span style={{ color: "#888", fontSize: "0.85em" }}>(16-char, from Google Account → Security → App Passwords)</span>
              <br />
              <input
                name="imap_password"
                type="password"
                required
                placeholder="abcd efgh ijkl mnop"
                autoComplete="off"
                style={{ width: "100%", maxWidth: "440px" }}
              />
            </label>
            <label>
              IMAP host <span style={{ color: "#888", fontSize: "0.85em" }}>(leave as-is for Gmail)</span>
              <br />
              <input
                name="imap_host"
                defaultValue="imap.gmail.com"
                style={{ width: "100%", maxWidth: "440px" }}
              />
            </label>
            <label>
              Mailbox folder <span style={{ color: "#888", fontSize: "0.85em" }}>(default: INBOX)</span>
              <br />
              <input name="imap_mailbox" defaultValue="INBOX" style={{ width: "100%", maxWidth: "240px" }} />
            </label>
            <label>
              company / sender hint <span style={{ color: "#888", fontSize: "0.85em" }}>(optional)</span>
              <br />
              <input name="company" placeholder="Reed / Adzuna / LinkedIn" style={{ width: "100%", maxWidth: "440px" }} />
            </label>
            <label>
              location hint <span style={{ color: "#888", fontSize: "0.85em" }}>(optional)</span>
              <br />
              <input name="location_text" placeholder="Aberdeen, Scotland" style={{ width: "100%", maxWidth: "440px" }} />
            </label>
            <label>
              <input type="checkbox" name="enabled" defaultChecked /> enabled
            </label>
          </div>
          <div style={{ marginTop: "10px" }}>
            <button type="submit">register IMAP source</button>
          </div>
        </form>
      </section>

      <section style={{ border: "1px solid #ccc", borderRadius: "8px", padding: "16px", marginBottom: "20px" }}>
        <h2>5) Run Pipeline Steps</h2>
        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
          <form action="/api/sources/ingest-run" method="post">
            <button type="submit">run ingest</button>
          </form>
          <form action="/api/sources/score-run" method="post">
            <input type="hidden" name="use_embeddings" value="false" />
            <button type="submit">run scoring</button>
          </form>
          <form action="/api/schedule-run" method="post">
            <button type="submit">run scheduled cycle</button>
          </form>
        </div>
      </section>

      <section style={{ border: "1px solid #ccc", borderRadius: "8px", padding: "16px", marginBottom: "20px" }}>
        <h2>6) Advanced Source JSON (optional)</h2>
        <p>Use this if you want to register multiple sources in one submit.</p>
        <form action="/api/sources/register" method="post">
          <textarea
            name="sources_json"
            defaultValue={ADVANCED_SOURCES_JSON}
            rows={14}
            style={{ width: "100%", fontFamily: "monospace", fontSize: "12px" }}
          />
          <div style={{ marginTop: "10px" }}>
            <button type="submit">register from json</button>
          </div>
        </form>
      </section>

      <section style={{ border: "1px solid #ccc", borderRadius: "8px", padding: "16px", marginBottom: "20px" }}>
        <h2>Configured Sources</h2>
        {sources.length === 0 ? (
          <p>none registered yet</p>
        ) : (
          <ul>
            {sources.map((source) => (
              <li key={source.id}>
                #{source.id} {source.name} ({source.type}) - {source.enabled ? "enabled" : "disabled"}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section style={{ border: "1px solid #ccc", borderRadius: "8px", padding: "16px" }}>
        <h2>Recent Scheduled Runs</h2>
        {runs.length === 0 ? (
          <p>no scheduled runs logged yet</p>
        ) : (
          <ul>
            {runs.map((run) => (
              <li key={run.run_id}>
                {run.status} | attempts: {run.attempts} | started: {run.started_at} | error: {run.error || "none"}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
