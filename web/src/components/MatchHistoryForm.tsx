"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { requestAnalysis } from "@/lib/cloud-api";

export function MatchHistoryForm() {
  const router = useRouter();
  const [matchId, setMatchId] = useState("");
  const [summonerName, setSummonerName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!matchId.trim() || !summonerName.trim()) return;

    setLoading(true);
    setError(null);

    try {
      await requestAnalysis(matchId.trim(), summonerName.trim());
      router.push(`/dashboard/history/${encodeURIComponent(matchId.trim())}`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label className="text-xs text-[#555] font-medium uppercase tracking-widest">
            Match ID
          </label>
          <input
            type="text"
            value={matchId}
            onChange={(e) => {
              // Auto-prefix bare numbers with EUW1_ as a convenience
              const v = e.target.value;
              if (/^\d+$/.test(v)) {
                setMatchId(`EUW1_${v}`);
              } else {
                setMatchId(v);
              }
            }}
            placeholder="EUW1_7821647780"
            className="w-full bg-[#0A0A0F] border border-[#1E1E2A] rounded-lg px-3 py-2.5 text-sm text-white placeholder:text-[#333] focus:outline-none focus:border-[#E24B4A]/50 transition-colors"
            disabled={loading}
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-xs text-[#555] font-medium uppercase tracking-widest">
            Riot ID
          </label>
          <input
            type="text"
            value={summonerName}
            onChange={(e) => setSummonerName(e.target.value)}
            placeholder="Name#EUW"
            className="w-full bg-[#0A0A0F] border border-[#1E1E2A] rounded-lg px-3 py-2.5 text-sm text-white placeholder:text-[#333] focus:outline-none focus:border-[#E24B4A]/50 transition-colors"
            disabled={loading}
          />
        </div>
      </div>

      {error && (
        <p className="text-sm text-[#E24B4A]">{error}</p>
      )}

      <button
        type="submit"
        disabled={loading || !matchId.trim() || !summonerName.trim()}
        className="bg-[#E24B4A] hover:bg-[#d03d3c] disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-semibold px-5 py-2.5 rounded-lg transition-colors flex items-center gap-2"
      >
        {loading ? (
          <>
            <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Analysing…
          </>
        ) : (
          "Analyse match"
        )}
      </button>

      {loading && (
        <p className="text-xs text-[#444]">
          Fetching match timeline and generating coaching — this takes 10–20 seconds.
        </p>
      )}
    </form>
  );
}
