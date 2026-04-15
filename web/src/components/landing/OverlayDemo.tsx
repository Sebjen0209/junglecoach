"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

type Priority = "high" | "medium" | "low";

interface LaneState {
  ally: string;
  enemy: string;
  priority: Priority;
  reason: string;
}

interface DemoState {
  minute: number;
  top: LaneState;
  mid: LaneState;
  bot: LaneState;
}

const DEMO_STATES: DemoState[] = [
  {
    minute: 8,
    top: { ally: "Riven", enemy: "Gangplank", priority: "high", reason: "Hard counter early. Kill pressure at level 6." },
    mid: { ally: "Azir", enemy: "Zed", priority: "medium", reason: "Survive to late. Avoid pre-6 all-ins." },
    bot: { ally: "Jinx", enemy: "Caitlyn", priority: "low", reason: "Even lane. Save resources for top." },
  },
  {
    minute: 11,
    top: { ally: "Riven", enemy: "Gangplank", priority: "high", reason: "Riven hit 6. Lethal with your gank." },
    mid: { ally: "Azir", enemy: "Zed", priority: "high", reason: "Zed burnt flash. Easy setup for kill." },
    bot: { ally: "Jinx", enemy: "Caitlyn", priority: "low", reason: "Caitlyn winning CS. Don't overcommit." },
  },
  {
    minute: 15,
    top: { ally: "Riven", enemy: "Gangplank", priority: "medium", reason: "GP hitting barrels. Trade carefully." },
    mid: { ally: "Azir", enemy: "Zed", priority: "low", reason: "Zed roaming. Ping and follow." },
    bot: { ally: "Jinx", enemy: "Caitlyn", priority: "high", reason: "Jinx 2 kills up. Dragon setup possible." },
  },
];

const PRIORITY_CONFIG: Record<Priority, { border: string; bg: string; label: string; dot: string; text: string }> = {
  high:   { border: "border-l-[#E24B4A]", bg: "bg-[#E24B4A]/8",  label: "HIGH", dot: "bg-[#E24B4A]", text: "text-[#E24B4A]" },
  medium: { border: "border-l-[#EF9F27]", bg: "bg-[#EF9F27]/8",  label: "MED",  dot: "bg-[#EF9F27]", text: "text-[#EF9F27]" },
  low:    { border: "border-l-[#3A3A3A]", bg: "bg-transparent",   label: "LOW",  dot: "bg-[#3A3A3A]", text: "text-[#555]" },
};

function LaneCard({ lane, label, index }: { lane: LaneState; label: string; index: number }) {
  const cfg = PRIORITY_CONFIG[lane.priority];
  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: index * 0.06 }}
      className={`border-l-2 ${cfg.border} ${cfg.bg} px-3 py-2.5 rounded-r-md`}
    >
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-bold text-[#444] uppercase tracking-wider w-6">{label}</span>
          <span className="text-[11px] text-white font-semibold">{lane.ally}</span>
          <span className="text-[9px] text-[#333]">vs</span>
          <span className="text-[11px] text-[#555]">{lane.enemy}</span>
        </div>
        <div className="flex items-center gap-1">
          <div className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
          <span className={`text-[9px] font-bold tracking-widest ${cfg.text}`}>{cfg.label}</span>
        </div>
      </div>
      <p className="text-[10px] text-[#444] leading-relaxed pl-[30px]">{lane.reason}</p>
    </motion.div>
  );
}

export function OverlayDemo() {
  const [idx, setIdx] = useState(0);
  const current = DEMO_STATES[idx];

  useEffect(() => {
    const t = setInterval(() => setIdx((i) => (i + 1) % DEMO_STATES.length), 3000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="relative">
      <div className="absolute -inset-8 bg-[#E24B4A]/5 blur-3xl rounded-full pointer-events-none" />
      <div className="relative bg-[rgba(10,10,15,0.95)] border border-[#1E1E2A] rounded-xl p-4 w-[290px] shadow-2xl">

        {/* Window chrome */}
        <div className="flex items-center justify-between mb-3 pb-2.5 border-b border-[#1A1A24]">
          <span className="text-xs font-bold text-white tracking-tight">
            JungleCoach<span className="text-[#E24B4A]">.</span>
          </span>
          <div className="flex items-center gap-2">
            <AnimatePresence mode="wait">
              <motion.span
                key={current.minute}
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 4 }}
                className="text-[10px] text-[#444] font-mono tabular-nums"
              >
                {String(current.minute).padStart(2, "0")}:00
              </motion.span>
            </AnimatePresence>
            <div className="w-1.5 h-1.5 rounded-full bg-[#22c55e] animate-pulse" />
          </div>
        </div>

        {/* Lane cards */}
        <AnimatePresence mode="wait">
          <motion.div
            key={idx}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="space-y-2"
          >
            <LaneCard lane={current.top} label="Top" index={0} />
            <LaneCard lane={current.mid} label="Mid" index={1} />
            <LaneCard lane={current.bot} label="Bot" index={2} />
          </motion.div>
        </AnimatePresence>

        {/* Footer */}
        <div className="mt-3 pt-2.5 border-t border-[#1A1A24] flex items-center gap-1.5">
          <div className="w-1 h-1 rounded-full bg-[#E24B4A] animate-ping" />
          <span className="text-[9px] text-[#333] tracking-wide">Live — refreshing every 5s</span>
        </div>
      </div>
    </div>
  );
}
