import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const sourcesJson = String(formData.get("sources_json") ?? "").trim();
  if (!sourcesJson) {
    return NextResponse.json({ error: "missing sources_json" }, { status: 400 });
  }

  let payload: unknown;
  try {
    payload = JSON.parse(sourcesJson);
  } catch {
    return NextResponse.json({ error: "invalid JSON for sources_json" }, { status: 400 });
  }

  const response = await fetch(`${API_BASE}/sources/register`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.text();
    return NextResponse.json({ error: "register failed", detail: body }, { status: response.status });
  }

  const referer = request.headers.get("referer") ?? "/ops";
  return NextResponse.redirect(referer);
}
