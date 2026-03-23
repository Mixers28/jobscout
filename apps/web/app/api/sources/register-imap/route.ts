import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const sourceName = String(formData.get("source_name") ?? "").trim();
  const imapUsername = String(formData.get("imap_username") ?? "").trim();
  const imapPassword = String(formData.get("imap_password") ?? "").trim();
  const imapHost = String(formData.get("imap_host") ?? "imap.gmail.com").trim();
  const imapPort = parseInt(String(formData.get("imap_port") ?? "993"), 10);
  const imapMailbox = String(formData.get("imap_mailbox") ?? "INBOX").trim() || "INBOX";
  const company = String(formData.get("company") ?? "").trim();
  const locationText = String(formData.get("location_text") ?? "").trim();
  const enabled = formData.get("enabled") === "on";

  if (!sourceName) {
    return NextResponse.json({ error: "missing source_name" }, { status: 400 });
  }
  if (!imapUsername || !imapPassword) {
    return NextResponse.json({ error: "missing imap_username or imap_password" }, { status: 400 });
  }

  const configJson: Record<string, unknown> = {
    imap_host: imapHost,
    imap_port: imapPort,
    imap_username: imapUsername,
    imap_password: imapPassword,
    imap_use_ssl: true,
    imap_mailbox: imapMailbox,
  };
  if (company) configJson.company = company;
  if (locationText) configJson.location_text = locationText;

  const payload = [
    {
      name: sourceName,
      type: "email_alert",
      enabled,
      config_json: configJson,
    },
  ];

  const response = await fetch(`${API_BASE}/sources/register`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.text();
    return NextResponse.json({ error: "register IMAP source failed", detail: body }, { status: response.status });
  }

  const referer = request.headers.get("referer") ?? "/ops";
  return NextResponse.redirect(referer);
}
