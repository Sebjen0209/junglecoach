import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase-server";

export const maxDuration = 90;

const CLOUD_API_URL =
  process.env.CLOUD_API_URL ?? "http://localhost:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: { matchId: string } }
) {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const { matchId } = params;
  const sp = request.nextUrl.searchParams;

  const url = new URL(`/postgame/${encodeURIComponent(matchId)}`, CLOUD_API_URL);
  if (sp.get("summoner_name")) url.searchParams.set("summoner_name", sp.get("summoner_name")!);
  if (sp.get("puuid")) url.searchParams.set("puuid", sp.get("puuid")!);

  let res: Response;
  try {
    res = await fetch(url.toString(), {
      headers: { Authorization: `Bearer ${session.access_token}` },
      // Cloud API can take a while — Riot fetch + Claude (~60s typical)
      signal: AbortSignal.timeout(90_000),
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Cloud API unreachable";
    return NextResponse.json({ detail: msg }, { status: 503 });
  }

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
