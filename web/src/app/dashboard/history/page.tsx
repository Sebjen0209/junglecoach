import Link from "next/link";
import { createClient } from "@/lib/supabase-server";
import { MatchHistoryForm } from "@/components/MatchHistoryForm";
import type { AnalysisSummary } from "@/lib/cloud-api";

export default async function HistoryPage() {
  const supabase = createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { data: rows } = await supabase
    .from("post_game_analyses")
    .select(
      "match_id, jungler_champion, analysed_at, gank_count, objective_count, pathing_issue_count, created_at"
    )
    .eq("user_id", user!.id)
    .order("created_at", { ascending: false })
    .limit(50);

  const analyses = (rows ?? []) as AnalysisSummary[];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Match History</h1>
        <p className="text-sm text-[#8080A0] mt-1">
          Post-game jungle coaching from your recent matches.
        </p>
      </div>

      {/* Submit form */}
      <div className="bg-[#0E0E18] border border-[#1C1C2A] rounded-xl p-6">
        <p className="text-[10px] font-bold text-[#46465C] uppercase tracking-[0.15em] mb-3">Analyse a match</p>
        <p className="text-sm text-[#8080A0] mb-5">
          Paste a match ID from your profile on{" "}
          <a
            href="https://www.op.gg"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#E24B4A] hover:text-[#d03d3c] transition-colors"
          >
            op.gg
          </a>{" "}
          or the League client.
        </p>
        <MatchHistoryForm />
      </div>

      {/* Past analyses */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <p className="text-[10px] font-bold text-[#46465C] uppercase tracking-[0.15em]">Past analyses</p>
          <span className="text-[10px] font-bold text-[#46465C] bg-[#0E0E18] border border-[#1C1C2A] px-2 py-0.5 rounded-full">
            {analyses.length}
          </span>
        </div>

        {analyses.length === 0 ? (
          <div className="bg-[#0E0E18] border border-[#1C1C2A] rounded-xl p-10 text-center">
            <p className="text-sm text-[#46465C]">No analyses yet.</p>
            <p className="text-xs text-[#2A2A3A] mt-1">Submit your first match ID above.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {analyses.map((a) => (
              <Link
                key={a.match_id}
                href={`/dashboard/history/${encodeURIComponent(a.match_id)}`}
                className="flex items-center justify-between bg-[#0E0E18] border border-[#1C1C2A] hover:border-[#E24B4A]/20 rounded-xl px-5 py-4 transition-colors group"
              >
                <div className="flex items-center gap-4">
                  <div className="w-9 h-9 rounded-lg bg-[#07070D] border border-[#1C1C2A] flex items-center justify-center text-[10px] font-bold text-[#46465C]">
                    JG
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">
                      {a.jungler_champion ?? "Unknown"}
                    </p>
                    <p className="text-xs text-[#46465C] font-mono mt-0.5">
                      {a.match_id}
                    </p>
                  </div>
                </div>

                <div className="hidden sm:flex items-center gap-5 text-xs text-[#46465C]">
                  <span><span className="text-white font-medium">{a.gank_count}</span> ganks</span>
                  <span><span className="text-white font-medium">{a.objective_count}</span> obj</span>
                  <span><span className="text-[#E24B4A] font-medium">{a.pathing_issue_count}</span> issues</span>
                  <span>{new Date(a.analysed_at).toLocaleDateString("en-GB")}</span>
                </div>

                <span className="text-[#1C1C2A] group-hover:text-[#8080A0] transition-colors ml-4">→</span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
