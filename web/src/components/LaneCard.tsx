"use client";

import { useState } from "react";
import { PriorityBadge } from "./PriorityBadge";
import type { LaneData } from "@/lib/api";

interface LaneCardProps {
  lane: "top" | "mid" | "bot";
  data: LaneData;
}

const PRIORITY_ACCENT: Record<string, { border: string; glow: string }> = {
  high:   { border: "#00e5ff", glow: "rgba(0,229,255,0.12)" },
  medium: { border: "#f0c040", glow: "rgba(240,192,64,0.10)" },
  low:    { border: "rgba(26,26,74,0.8)", glow: "transparent" },
};

const LANE_LABELS = { top: "TOP", mid: "MID", bot: "BOT" };

export function LaneCard({ lane, data }: LaneCardProps) {
  const [expanded, setExpanded] = useState(false);
  const accent = PRIORITY_ACCENT[data.priority] ?? PRIORITY_ACCENT.low;

  return (
    <button
      onClick={() => setExpanded((v) => !v)}
      className="w-full text-left rounded-xl border-l-2 transition-all duration-200 focus:outline-none"
      style={{
        background: "rgba(13,13,43,0.7)",
        border: `1px solid rgba(26,26,74,0.8)`,
        borderLeftColor: accent.border,
        borderLeftWidth: 3,
        backdropFilter: "blur(12px)",
        boxShadow: expanded ? `0 0 30px ${accent.glow}` : "none",
        padding: "1rem",
      }}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <span
            className="sub-heading text-[10px] font-bold tracking-widest shrink-0"
            style={{ color: accent.border === "rgba(26,26,74,0.8)" ? "#3949ab" : accent.border }}
          >
            {LANE_LABELS[lane]}
          </span>
          <span className="text-sm truncate" style={{ color: "#f0f2ff" }}>
            {data.ally_champion}
            <span style={{ color: "#3949ab", margin: "0 6px" }}>vs</span>
            {data.enemy_champion}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="sub-heading text-[10px] tracking-widest" style={{ color: "#c5cae9" }}>
            {(data.matchup_winrate * 100).toFixed(0)}%
          </span>
          <PriorityBadge priority={data.priority} />
        </div>
      </div>

      {expanded && (
        <p
          className="mt-3 text-sm leading-relaxed border-t pt-3"
          style={{ color: "#c5cae9", borderColor: "rgba(26,26,74,0.8)" }}
        >
          {data.reason}
        </p>
      )}
    </button>
  );
}
