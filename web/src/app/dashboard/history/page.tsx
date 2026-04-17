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
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Match History</h1>
        <p className="text-sm text-[#555] mt-1">
          Post-game jungle coaching from your recent matches.
        </p>
      </div>

      {/* Submit form */}
      <div className="bg-[#13131A] border border-[#1E1E2A] rounded-xl p-6">
        <h2 className="text-base font-bold text-white mb-1">Analyse a match</h2>
        <p className="text-sm text-[#555] mb-4">
          Paste a match ID from your profile on{" "}
          <a
            href="https://www.op.gg"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#E24B4A] hover:underline"
          >
            op.gg
          </a>{" "}
          or the League client.
        </p>
        <MatchHistoryForm />
      </div>

      {/* Past analyses */}
      <div>
        <h2 className="text-base font-bold text-white mb-4">
          Past analyses{" "}
          <span className="text-[#444] font-normal text-sm">
            ({analyses.length})
          </span>
        </h2>

        {analyses.length === 0 ? (
          <div className="bg-[#13131A] border border-[#1E1E2A] rounded-xl p-8 text-center">
            <p className="text-[#444] text-sm">No analyses yet.</p>
            <p className="text-[#333] text-xs mt-1">
              Submit your first match ID above.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {analyses.map((a) => (
              <Link
                key={a.match_id}
                href={`/dashboard/history/${encodeURIComponent(a.match_id)}`}
                className="flex items-center justify-between bg-[#13131A] border border-[#1E1E2A] hover:border-[#2E2E3A] rounded-xl px-5 py-4 transition-colors group"
              >
                <div className="flex items-center gap-4">
                  <div className="w-9 h-9 rounded-lg bg-[#0A0A0F] border border-[#1E1E2A] flex items-center justify-center text-xs font-bold text-[#555]">
                    JG
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">
                      {a.jungler_champion ?? "Unknown"}
                    </p>
                    <p className="text-xs text-[#444] font-mono mt-0.5">
                      {a.match_id}
                    </p>
                  </div>
                </div>

                <div className="hidden sm:flex items-center gap-6 text-xs text-[#555]">
                  <span>
                    <span className="text-white font-medium">{a.gank_count}</span>{" "}
                    ganks
                  </span>
                  <span>
                    <span className="text-white font-medium">
                      {a.objective_count}
                    </span>{" "}
                    objectives
                  </span>
                  <span>
                    <span className="text-[#E24B4A] font-medium">
                      {a.pathing_issue_count}
                    </span>{" "}
                    issues
                  </span>
                  <span className="text-[#333]">
                    {new Date(a.analysed_at).toLocaleDateString("en-GB")}
                  </span>
                </div>

                <span className="text-[#333] group-hover:text-[#555] transition-colors text-lg ml-4">
                  →
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
