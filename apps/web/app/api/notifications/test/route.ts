import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  const response = await fetch(`${API_BASE}/jobs/notifications/test`, {
    method: "POST",
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.text();
    return NextResponse.json({ error: "test notification failed", detail: body }, { status: response.status });
  }

  const referer = request.headers.get("referer") ?? "/ops";
  return NextResponse.redirect(referer);
}
