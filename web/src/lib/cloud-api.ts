// Types and fetch helpers for the JungleCoach Cloud API.
// API routes in /api/postgame proxy requests server-side with auth.

export interface CoachingMoment {
  timestamp_str: string;
  what_happened: string;
  was_good_decision: boolean;
  reasoning: string;
  suggestion: string | null;
}

export interface PostGameAnalysis {
  match_id: string;
  jungler_champion: string;
  analysed_at: string;
  gank_count: number;
  objective_count: number;
  pathing_issue_count: number;
  moments: CoachingMoment[];
}

// Lightweight summary row as stored/returned from Supabase
export interface AnalysisSummary {
  match_id: string;
  jungler_champion: string;
  analysed_at: string;
  gank_count: number;
  objective_count: number;
  pathing_issue_count: number;
  created_at: string;
}

export async function requestAnalysis(
  matchId: string,
  summonerName: string
): Promise<PostGameAnalysis> {
  const params = new URLSearchParams({ summoner_name: summonerName });
  const res = await fetch(`/api/postgame/${encodeURIComponent(matchId)}?${params}`, {
    method: "GET",
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      body?.detail ?? `Analysis failed (${res.status})`
    );
  }

  return res.json() as Promise<PostGameAnalysis>;
}
