import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const useEmbeddingsRaw = String(formData.get("use_embeddings") ?? "false").toLowerCase();
  const useEmbeddings = useEmbeddingsRaw === "true";

  const response = await fetch(`${API_BASE}/jobs/score/run`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ use_embeddings: useEmbeddings }),
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.text();
    return NextResponse.json({ error: "score run failed", detail: body }, { status: response.status });
  }
  const referer = request.headers.get("referer") ?? "/ops";
  return NextResponse.redirect(referer);
}
