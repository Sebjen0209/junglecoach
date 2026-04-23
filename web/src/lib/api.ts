const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:7429";

export interface LaneData {
  ally_champion: string;
  enemy_champion: string;
  matchup_winrate: number;
  priority: "high" | "medium" | "low";
  reason: string | null;
  score: number;
}

export interface MacroHint {
  type: "objective" | "lane" | "trade" | "state";
  urgency: "critical" | "high" | "medium";
  headline: string;
  detail: string;
}

export interface AnalysisResponse {
  game_detected: boolean;
  game_minute: number | null;
  patch: string | null;
  analysed_at: string | null;
  analysis_mode: "laning" | "macro" | null;
  lanes: {
    top: LaneData;
    mid: LaneData;
    bot: LaneData;
  } | null;
  macro_hints: MacroHint[] | null;
}

export interface SubscriptionCheckResponse {
  plan: string;
  valid: boolean;
  expires_at: string | null;
}

export async function fetchAnalysis(): Promise<AnalysisResponse> {
  const res = await fetch(`${API_BASE}/analysis`);
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return res.json() as Promise<AnalysisResponse>;
}

export async function fetchSubscriptionStatus(
  token: string
): Promise<SubscriptionCheckResponse> {
  const res = await fetch(`${API_BASE}/subscription`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`Subscription check failed: ${res.status}`);
  return res.json() as Promise<SubscriptionCheckResponse>;
}
