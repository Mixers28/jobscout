import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const sourceName = String(formData.get("source_name") ?? "").trim();
  const feedUrl = String(formData.get("feed_url") ?? "").trim();
  const company = String(formData.get("company") ?? "").trim();
  const enabled = formData.get("enabled") === "on";

  if (!sourceName || !feedUrl) {
    return NextResponse.json({ error: "missing source_name or feed_url" }, { status: 400 });
  }

  try {
    // Validate feed URL format early for user feedback.
    new URL(feedUrl);
  } catch {
    return NextResponse.json({ error: "invalid feed_url" }, { status: 400 });
  }

  const payload = [
    {
      name: sourceName,
      type: "rss",
      enabled,
      config_json: {
        feed_url: feedUrl,
        company,
      },
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
    return NextResponse.json({ error: "register rss source failed", detail: body }, { status: response.status });
  }

  const referer = request.headers.get("referer") ?? "/ops";
  return NextResponse.redirect(referer);
}
