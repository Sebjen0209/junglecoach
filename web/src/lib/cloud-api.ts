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
  moments: CoachingMoment[];
  created_at: string;
}

export interface RankedStats {
  tier: string;
  rank: string;
  lp: number;
  wins: number;
  losses: number;
}

export interface PlayerProfile {
  summoner_name: string;
  summoner_level: number;
  profile_icon_id: number;
  ranked_solo: RankedStats | null;
}

export interface ParticipantSummary {
  champion: string;
  champion_id: number;
  summoner_name: string;
  position: string;
  team_id: number;
  kills: number;
  deaths: number;
  assists: number;
  cs: number;
  damage_dealt: number;
  gold_earned: number;
  vision_score: number;
  items: number[];
  trinket: number | null;
  summoner_spell_1: number;
  summoner_spell_2: number;
  is_self: boolean;
}

export interface MatchEntry {
  match_id: string;
  champion: string;
  champion_id: number;
  position: string;
  win: boolean;
  kills: number;
  deaths: number;
  assists: number;
  cs: number;
  vision_score: number;
  items: number[];
  trinket: number | null;
  summoner_spell_1: number;
  summoner_spell_2: number;
  kill_participation: number;
  enemy_jungler: string | null;
  enemy_jungler_id: number | null;
  enemy_items: number[];
  game_duration_seconds: number;
  game_start_timestamp: number;
  has_analysis: boolean;
  participants: ParticipantSummary[];
}

export interface MatchHistoryResponse {
  summoner_name: string;
  ddragon_version: string;
  player_profile: PlayerProfile | null;
  matches: MatchEntry[];
}

export async function fetchMatchHistory(
  summonerName: string,
  region = "europe",
  count = 10
): Promise<MatchHistoryResponse> {
  const params = new URLSearchParams({
    summoner_name: summonerName,
    region,
    count: String(count),
  });
  const res = await fetch(`/api/match-history?${params}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? `Match history failed (${res.status})`);
  }
  return res.json() as Promise<MatchHistoryResponse>;
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
