import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const jobId = String(formData.get("job_id") ?? "").trim();
  const stage = String(formData.get("stage") ?? "").trim();
  const outcome = String(formData.get("outcome") ?? "").trim();

  if (!jobId) {
    return NextResponse.json({ error: "missing job_id" }, { status: 400 });
  }

  const payload: Record<string, string> = {};
  if (stage) {
    payload.stage = stage;
  }
  if (outcome) {
    payload.outcome = outcome;
  }

  const response = await fetch(`${API_BASE}/jobs/${encodeURIComponent(jobId)}/tracking`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.text();
    return NextResponse.json({ error: "tracking update failed", detail: body }, { status: response.status });
  }

  const referer = request.headers.get("referer") ?? "/";
  return NextResponse.redirect(referer);
}
