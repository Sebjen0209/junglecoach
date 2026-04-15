"use client";

import { useState } from "react";
import { PriorityBadge } from "./PriorityBadge";
import type { LaneData } from "@/lib/api";

interface LaneCardProps {
  lane: "top" | "mid" | "bot";
  data: LaneData;
}

const BORDER_COLOURS = {
  high: "border-l-[#E24B4A]",
  medium: "border-l-[#EF9F27]",
  low: "border-l-[#444441]",
};

const LANE_LABELS = { top: "Top", mid: "Mid", bot: "Bot" };

export function LaneCard({ lane, data }: LaneCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <button
      onClick={() => setExpanded((v) => !v)}
      className={`w-full text-left bg-[#13131A] border border-[#1E1E2A] border-l-4 ${BORDER_COLOURS[data.priority]} rounded-lg p-4 transition-all hover:border-[#2A2A3A] focus:outline-none`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-xs font-semibold text-[#666] uppercase tracking-widest w-6 shrink-0">
            {LANE_LABELS[lane]}
          </span>
          <span className="text-sm text-white font-medium truncate">
            {data.ally_champion}
            <span className="text-[#555] mx-1">vs</span>
            {data.enemy_champion}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs text-[#555]">
            {(data.matchup_winrate * 100).toFixed(0)}% WR
          </span>
          <PriorityBadge priority={data.priority} />
        </div>
      </div>

      {expanded && (
        <p className="mt-3 text-sm text-[#888] leading-relaxed border-t border-[#1E1E2A] pt-3">
          {data.reason}
        </p>
      )}
    </button>
  );
}
