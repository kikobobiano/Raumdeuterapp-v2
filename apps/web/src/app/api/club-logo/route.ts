import { NextRequest, NextResponse } from "next/server";

/** Wyscout team photo CDN only — avoid open proxy */
const WYSCOUT_TEAM_IMG = /^https:\/\/cdn[0-9]*\.wyscout\.com\/photos\/team\//i;

export async function GET(req: NextRequest) {
  const raw = req.nextUrl.searchParams.get("url");
  if (!raw || !WYSCOUT_TEAM_IMG.test(raw)) {
    return new NextResponse("Invalid url", { status: 400 });
  }

  const upstream = await fetch(raw, {
    headers: { Accept: "image/*,*/*;q=0.8" },
    next: { revalidate: 86_400 },
  });

  if (!upstream.ok) {
    return new NextResponse("Upstream error", { status: 502 });
  }

  const ct = upstream.headers.get("content-type") ?? "image/png";
  const stream = upstream.body;
  if (stream) {
    return new NextResponse(stream, {
      headers: {
        "Content-Type": ct,
        "Cache-Control": "public, max-age=86400, stale-while-revalidate=3600",
      },
    });
  }

  const body = await upstream.arrayBuffer();
  return new NextResponse(body, {
    headers: {
      "Content-Type": ct,
      "Cache-Control": "public, max-age=86400, stale-while-revalidate=3600",
    },
  });
}
