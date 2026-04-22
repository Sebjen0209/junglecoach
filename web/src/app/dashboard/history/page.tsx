import Link from "next/link";
import { createClient } from "@/lib/supabase-server";
import { MatchHistoryForm } from "@/components/MatchHistoryForm";
import type { AnalysisSummary } from "@/lib/cloud-api";

export default async function HistoryPage() {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();

  const { data: rows } = await supabase
    .from("post_game_analyses")
    .select("match_id, jungler_champion, analysed_at, gank_count, objective_count, pathing_issue_count, created_at")
    .eq("user_id", user!.id)
    .order("created_at", { ascending: false })
    .limit(50);

  const analyses = (rows ?? []) as AnalysisSummary[];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="arcane-heading text-2xl font-bold" style={{ color: "#f0f2ff" }}>Match History</h1>
        <p className="text-sm mt-1" style={{ color: "#c5cae9" }}>
          Post-game jungle coaching from your recent matches.
        </p>
      </div>

      {/* Submit form */}
      <div
        className="rounded-xl p-6 border"
        style={{
          background: "rgba(20,20,60,0.75)",
          borderColor: "rgba(80,90,180,0.35)",
          backdropFilter: "blur(16px)",
        }}
      >
        <p className="sub-heading text-[10px] font-bold tracking-[0.2em] mb-2" style={{ color: "#7986cb" }}>
          ANALYSE A MATCH
        </p>
        <p className="text-sm mb-5" style={{ color: "#c5cae9" }}>
          Paste a match ID from your profile on{" "}
          <a
            href="https://www.op.gg"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "#00e5ff" }}
            className="hover:underline transition-colors"
          >
            op.gg
          </a>{" "}
          or the League client.
        </p>
        <MatchHistoryForm />
      </div>

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
