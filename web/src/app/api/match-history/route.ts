import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase-server";

const CLOUD_API_URL = process.env.CLOUD_API_URL ?? "http://localhost:8000";

export async function GET(request: NextRequest) {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const sp = request.nextUrl.searchParams;
  const summonerName = sp.get("summoner_name");
  if (!summonerName) {
    return NextResponse.json({ detail: "summoner_name is required" }, { status: 400 });
  }

  const url = new URL("/match-history", CLOUD_API_URL);
  url.searchParams.set("summoner_name", summonerName);
  if (sp.get("region")) url.searchParams.set("region", sp.get("region")!);
  if (sp.get("count")) url.searchParams.set("count", sp.get("count")!);

  let res: Response;
  try {
    res = await fetch(url.toString(), {
      headers: { Authorization: `Bearer ${session.access_token}` },
      signal: AbortSignal.timeout(30_000),
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Cloud API unreachable";
    return NextResponse.json({ detail: msg }, { status: 503 });
  }

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
