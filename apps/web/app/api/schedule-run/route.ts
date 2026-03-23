import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  const response = await fetch(`${API_BASE}/jobs/schedule/run`, {
    method: "POST",
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.text();
    return NextResponse.json({ error: "schedule run failed", detail: body }, { status: response.status });
  }

  const referer = request.headers.get("referer") ?? "/";
  return NextResponse.redirect(referer);
}
