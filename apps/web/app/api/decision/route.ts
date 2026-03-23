import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const jobId = String(formData.get("job_id") ?? "").trim();
  const decision = String(formData.get("decision") ?? "").trim();

  if (!jobId || !decision) {
    return NextResponse.json({ error: "missing job_id or decision" }, { status: 400 });
  }

  const response = await fetch(`${API_BASE}/jobs/${encodeURIComponent(jobId)}/decision`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ decision }),
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.text();
    return NextResponse.json({ error: "decision update failed", detail: body }, { status: response.status });
  }

  const referer = request.headers.get("referer") ?? "/";
  return NextResponse.redirect(referer);
}
