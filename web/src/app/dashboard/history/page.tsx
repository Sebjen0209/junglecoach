import Link from "next/link";
import { createClient } from "@/lib/supabase-server";
import { ManualAnalysisSection } from "@/components/ManualAnalysisSection";
import { RecentMatchesLookup } from "@/components/RecentMatchesLookup";
import type { AnalysisSummary } from "@/lib/cloud-api";

const PLAN_LIMITS: Record<string, { count: number; days: number }> = {
  free:    { count: 2,  days: 30 },
  premium: { count: 15, days: 7 },
  pro:     { count: 35, days: 7 },
};

export default async function HistoryPage() {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();

  const [{ data: rows }, { data: sub }, { count: usedCount }] = await Promise.all([
    supabase
      .from("post_game_analyses")
      .select("match_id, jungler_champion, analysed_at, gank_count, objective_count, pathing_issue_count, created_at")
      .eq("user_id", user!.id)
      .order("created_at", { ascending: false })
      .limit(50),
    supabase
      .from("subscriptions")
      .select("plan, status")
      .eq("user_id", user!.id)
      .maybeSingle(),
    supabase
      .from("post_game_analyses")
      .select("id", { count: "exact", head: true })
      .eq("user_id", user!.id)
      .gte("created_at", new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString()),
  ]);

  const plan = (sub && ["active", "cancelling", "past_due"].includes(sub.status ?? ""))
    ? (sub.plan ?? "free")
    : "free";
  const limits = PLAN_LIMITS[plan] ?? PLAN_LIMITS.free;

  // For non-free plans, recount with the correct rolling window
  let used = usedCount ?? 0;
  if (plan !== "free" && limits.days !== 30) {
    const { count } = await supabase
      .from("post_game_analyses")
      .select("id", { count: "exact", head: true })
      .eq("user_id", user!.id)
      .gte("created_at", new Date(Date.now() - limits.days * 24 * 60 * 60 * 1000).toISOString());
    used = count ?? 0;
  }

  const remaining = Math.max(0, limits.count - used);
  const analyses = (rows ?? []) as AnalysisSummary[];

  const windowLabel = limits.days === 30 ? "month" : "week";
  const pctUsed = limits.count > 0 ? Math.min(100, (used / limits.count) * 100) : 0;
  const quotaColor = remaining === 0 ? "#f87171" : remaining <= 1 ? "#fb923c" : "#4ade80";

  return (
    <div className="space-y-6">
      {/* Header + quota */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="arcane-heading text-2xl font-bold" style={{ color: "#f0f2ff" }}>Match History</h1>
          <p className="text-sm mt-1" style={{ color: "#c5cae9" }}>
            Post-game jungle coaching from your recent matches.
          </p>
        </div>

        {/* Quota pill */}
        <div
          className="rounded-xl px-4 py-3 border flex-shrink-0"
          style={{
            background: "rgba(13,13,43,0.8)",
            borderColor: "rgba(80,90,180,0.3)",
            minWidth: 180,
          }}
        >
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-semibold" style={{ color: quotaColor }}>
              {remaining} left
            </span>
            <span className="text-xs" style={{ color: "#6b7280" }}>
              {used} / {limits.count} this {windowLabel}
            </span>
          </div>
          <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.07)" }}>
            <div
              className="h-full rounded-full transition-all"
              style={{ width: `${pctUsed}%`, background: quotaColor }}
            />
          </div>
          {remaining === 0 && (
            <div className="mt-2 flex items-center justify-between">
              <span className="text-xs" style={{ color: "#6b7280" }}>Limit reached</span>
              <a href="/billing" className="text-xs font-medium" style={{ color: "#67e8f9" }}>
                Upgrade →
              </a>
            </div>
          )}
          {plan !== "free" && (
            <p className="text-xs mt-1.5 capitalize" style={{ color: "#6b7280" }}>
              {plan} plan
            </p>
          )}
        </div>
      </div>

      {/* Recent matches lookup */}
      <div
        className="rounded-xl p-6 border"
        style={{
          background: "rgba(20,20,60,0.75)",
          borderColor: "rgba(80,90,180,0.35)",
          backdropFilter: "blur(16px)",
        }}
      >
        <p className="sub-heading text-[10px] font-bold tracking-[0.2em] mb-2" style={{ color: "#7986cb" }}>
          RECENT RANKED MATCHES
        </p>
        <p className="text-sm mb-5" style={{ color: "#c5cae9" }}>
          Enter your Riot ID to see your last 10 ranked games and analyse any of them.
        </p>
        <RecentMatchesLookup />
      </div>

      {/* Manual match ID — collapsed by default */}
      <ManualAnalysisSection />

      {/* Past analyses */}
      <div>
        <div className="flex items-center gap-3 mb-4">
          <p className="sub-heading text-[11px] font-bold tracking-[0.15em]" style={{ color: "#c5cae9" }}>
            PAST ANALYSES
          </p>
          <span
            className="sub-heading text-[10px] font-bold px-2 py-0.5 rounded-full border"
            style={{
              background: "rgba(26,26,74,0.5)",
              borderColor: "rgba(26,26,74,0.8)",
              color: "#c5cae9",
            }}
          >
            {analyses.length}
          </span>
        </div>

        {analyses.length === 0 ? (
          <div
            className="rounded-xl p-12 text-center border"
            style={{
              background: "rgba(13,13,43,0.7)",
              borderColor: "rgba(26,26,74,0.8)",
              backdropFilter: "blur(16px)",
            }}
          >
            <p className="text-sm" style={{ color: "#7986cb" }}>No analyses yet.</p>
            <p className="text-xs mt-1" style={{ color: "#1a1a4a" }}>Submit your first match ID above.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {analyses.map((a) => (
              <Link
                key={a.match_id}
                href={`/dashboard/history/${encodeURIComponent(a.match_id)}`}
                className="history-card flex items-center justify-between px-5 py-4 group"
              >
                <div className="flex items-center gap-4">
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center sub-heading text-[10px] font-bold border"
                    style={{
                      background: "rgba(0,229,255,0.06)",
                      borderColor: "rgba(0,229,255,0.15)",
                      color: "#00e5ff",
                    }}
                  >
                    JG
                  </div>
                  <div>
                    <p className="text-sm font-semibold" style={{ color: "#f0f2ff" }}>
                      {a.jungler_champion ?? "Unknown"}
                    </p>
                    <p className="text-xs font-mono mt-0.5" style={{ color: "#7986cb" }}>
                      {a.match_id}
                    </p>
                  </div>
                </div>

                <div className="hidden sm:flex items-center gap-5 sub-heading text-[11px] tracking-widest">
                  <span style={{ color: "#7986cb" }}>
                    <span style={{ color: "#f0f2ff" }} className="font-bold">{a.gank_count}</span> GANKS
                  </span>
                  <span style={{ color: "#7986cb" }}>
                    <span style={{ color: "#f0f2ff" }} className="font-bold">{a.objective_count}</span> OBJ
                  </span>
                  <span style={{ color: "#7986cb" }}>
                    <span style={{ color: "#ff3366" }} className="font-bold">{a.pathing_issue_count}</span> ISSUES
                  </span>
                  <span style={{ color: "#7986cb" }}>
                    {new Date(a.analysed_at).toLocaleDateString("en-GB")}
                  </span>
                </div>

                <span className="history-arrow ml-4 transition-colors" style={{ color: "#7986cb" }}>→</span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
