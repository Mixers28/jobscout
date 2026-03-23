import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const sourceName = String(formData.get("source_name") ?? "").trim();
  const pageUrl = String(formData.get("page_url") ?? "").trim();
  const company = String(formData.get("company") ?? "").trim();
  const allowedDomainInput = String(formData.get("allowed_domain") ?? "").trim().toLowerCase();
  const enabled = formData.get("enabled") === "on";

  if (!sourceName || !pageUrl) {
    return NextResponse.json({ error: "missing source_name or page_url" }, { status: 400 });
  }

  let parsedUrl: URL;
  try {
    parsedUrl = new URL(pageUrl);
  } catch {
    return NextResponse.json({ error: "invalid page_url" }, { status: 400 });
  }

  const allowedDomain = allowedDomainInput || parsedUrl.hostname.toLowerCase();
  const payload = [
    {
      name: sourceName,
      type: "whitelist_career_page",
      enabled,
      config_json: {
        company: company || sourceName,
        allowed_domains: allowedDomain ? [allowedDomain] : [],
        page_urls: [pageUrl],
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
    return NextResponse.json({ error: "register site source failed", detail: body }, { status: response.status });
  }

  const referer = request.headers.get("referer") ?? "/ops";
  return NextResponse.redirect(referer);
}
