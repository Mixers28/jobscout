import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const sourceName = String(formData.get("source_name") ?? "").trim();
  const company = String(formData.get("company") ?? "").trim();
  const locationText = String(formData.get("location_text") ?? "").trim();
  const emailBody = String(formData.get("email_body") ?? "").trim();
  const enabled = formData.get("enabled") === "on";

  if (!sourceName) {
    return NextResponse.json({ error: "missing source_name" }, { status: 400 });
  }
  if (!emailBody) {
    return NextResponse.json({ error: "missing email_body" }, { status: 400 });
  }

  const configJson: Record<string, unknown> = {
    messages: [emailBody],
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
    return NextResponse.json({ error: "register email source failed", detail: body }, { status: response.status });
  }

  const referer = request.headers.get("referer") ?? "/ops";
  return NextResponse.redirect(referer);
}
