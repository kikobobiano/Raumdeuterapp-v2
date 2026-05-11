import { NextRequest, NextResponse } from "next/server";

/** Wyscout player photo CDN — avoid open proxy */
const WYSCOUT_PLAYER_IMG = /^https:\/\/cdn[0-9]*\.wyscout\.com\/photos\/player\//i;
const WYSCOUT_PLAYER_PUBLIC =
  /^https:\/\/cdn[0-9]*\.wyscout\.com\/photos\/players\/public\/(?:g-?)?\d+_100x130\.png$/i;
/** Transfermarkt portrait CDN (CSV ``image_url`` from enrich_with_tm.py) */
const TRANSFERMARKT_PLAYER_IMG =
  /^https:\/\/img\.a\.transfermarkt\.technology\/portrait\//i;

export async function GET(req: NextRequest) {
  const raw = req.nextUrl.searchParams.get("url");
  const ok =
    raw &&
    (WYSCOUT_PLAYER_IMG.test(raw) ||
      WYSCOUT_PLAYER_PUBLIC.test(raw) ||
      TRANSFERMARKT_PLAYER_IMG.test(raw));
  if (!ok) {
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
