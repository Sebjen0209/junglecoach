import Link from "next/link";
import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase-server";
import { CoachingMomentCard } from "@/components/CoachingMomentCard";
import type { CoachingMoment } from "@/lib/cloud-api";

interface PageProps {
  params: { matchId: string };
}

interface AnalysisRow {
  match_id: string;
  jungler_champion: string;
  analysed_at: string;
  gank_count: number;
  objective_count: number;
  pathing_issue_count: number;
  moments: CoachingMoment[];
}

export default async function HistoryDetailPage({ params }: PageProps) {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const matchId = decodeURIComponent(params.matchId);

  const { data } = await supabase
    .from("post_game_analyses")
    .select("*")
    .eq("user_id", user!.id)
    .eq("match_id", matchId)
    .maybeSingle();

  if (!data) notFound();

  const analysis = data as AnalysisRow;
  const goodCount = analysis.moments.filter((m) => m.was_good_decision).length;
  const badCount = analysis.moments.filter((m) => !m.was_good_decision).length;

  return (
    <div className="space-y-6">
      <Link
        href="/dashboard/history"
        className="inline-flex items-center gap-1.5 text-sm text-[#46465C] hover:text-white transition-colors"
      >
        ← Back to history
      </Link>

      {/* Header */}
      <div className="bg-[#0E0E18] border border-[#1C1C2A] rounded-xl p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-5">
          <div>
            <p className="text-[10px] font-bold text-[#46465C] uppercase tracking-[0.15em] mb-2">Jungler</p>
            <h1 className="text-2xl font-bold text-white">{analysis.jungler_champion}</h1>
            <p className="text-xs text-[#46465C] font-mono mt-1">{matchId}</p>
          </div>
          <div className="flex gap-2">
            <Stat label="Ganks" value={analysis.gank_count} />
            <Stat label="Objectives" value={analysis.objective_count} />
          </div>
        </div>

        <div className="mt-5 pt-5 border-t border-[#1C1C2A] flex flex-wrap items-center gap-5">
          <div className="flex items-center gap-2 text-sm">
            <span className="w-2 h-2 rounded-full bg-green-500" />
            <span className="text-green-400 font-semibold">{goodCount}</span>
            <span className="text-[#46465C]">good decisions</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className="w-2 h-2 rounded-full bg-[#E24B4A]" />
            <span className="text-[#E24B4A] font-semibold">{badCount}</span>
            <span className="text-[#46465C]">missed opportunities</span>
          </div>
          <span className="text-[#46465C] text-xs ml-auto">
            {new Date(analysis.analysed_at).toLocaleString("en-GB")}
          </span>
        </div>
      </div>

      {/* Timeline */}
      <div>
        <p className="text-[10px] font-bold text-[#46465C] uppercase tracking-[0.15em] mb-6">Coaching timeline</p>
        {analysis.moments.length === 0 ? (
          <p className="text-sm text-[#46465C]">No moments recorded for this match.</p>
        ) : (
          <div>
            {analysis.moments.map((moment, i) => (
              <CoachingMomentCard key={i} moment={moment} index={i} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: number;
  accent?: boolean;
}) {
  return (
    <div className="bg-[#07070D] border border-[#1C1C2A] rounded-lg px-4 py-3 text-center min-w-[68px]">
      <p className={`text-xl font-bold ${accent ? "text-[#E24B4A]" : "text-white"}`}>
        {value}
      </p>
      <p className="text-[10px] text-[#46465C] mt-0.5 uppercase tracking-wider">{label}</p>
    </div>
  );
}
