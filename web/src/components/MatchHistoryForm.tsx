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
      router.push(`/dashboard/post-analysis/${encodeURIComponent(matchId.trim())}`);
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
          <label className="sub-heading text-[10px] tracking-widest" style={{ color: "#7986cb" }}>
            MATCH ID
          </label>
          <input
            type="text"
            value={matchId}
            onChange={(e) => {
              const v = e.target.value;
              setMatchId(/^\d+$/.test(v) ? `EUW1_${v}` : v);
            }}
            placeholder="EUW1_7821647780"
            disabled={loading}
            className="w-full rounded-lg px-3 py-2.5 text-sm transition-colors focus:outline-none"
            style={{
              background: "rgba(8,8,24,0.8)",
              border: "1px solid rgba(26,26,74,0.8)",
              color: "#e8eaf6",
            }}
            onFocus={e => (e.currentTarget.style.borderColor = "rgba(0,229,255,0.4)")}
            onBlur={e => (e.currentTarget.style.borderColor = "rgba(26,26,74,0.8)")}
          />
        </div>
        <div className="space-y-1.5">
          <label className="sub-heading text-[10px] tracking-widest" style={{ color: "#7986cb" }}>
            RIOT ID
          </label>
          <input
            type="text"
            value={summonerName}
            onChange={(e) => setSummonerName(e.target.value)}
            placeholder="Name#EUW"
            disabled={loading}
            className="w-full rounded-lg px-3 py-2.5 text-sm transition-colors focus:outline-none"
            style={{
              background: "rgba(8,8,24,0.8)",
              border: "1px solid rgba(26,26,74,0.8)",
              color: "#e8eaf6",
            }}
            onFocus={e => (e.currentTarget.style.borderColor = "rgba(0,229,255,0.4)")}
            onBlur={e => (e.currentTarget.style.borderColor = "rgba(26,26,74,0.8)")}
          />
        </div>
      </div>

      {error && (
        <p className="text-sm" style={{ color: "#ff3366" }}>{error}</p>
      )}

      <button
        type="submit"
        disabled={loading || !matchId.trim() || !summonerName.trim()}
        className="btn-arcane disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
      >
        {loading ? (
          <>
            <span className="w-3.5 h-3.5 border-2 border-[#080818]/30 border-t-[#080818] rounded-full animate-spin" />
            Analysing…
          </>
        ) : (
          "Analyse match"
        )}
      </button>

      {loading && (
        <p className="text-xs" style={{ color: "#7986cb" }}>
          Fetching match timeline and generating coaching — this takes 10–20 seconds.
        </p>
      )}
    </form>
  );
}
