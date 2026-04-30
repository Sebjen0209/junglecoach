"use client";

import { useState } from "react";
import { MatchHistoryForm } from "@/components/MatchHistoryForm";

export function ManualAnalysisSection() {
  const [open, setOpen] = useState(false);

  return (
    <div
      className="rounded-xl border overflow-hidden"
      style={{
        background: "rgba(20,20,60,0.75)",
        borderColor: "rgba(80,90,180,0.35)",
        backdropFilter: "blur(16px)",
      }}
    >
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-6 py-4 text-left hover:bg-white/[0.02] transition-colors"
      >
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#7986cb" }}>
            Analyse by Match ID
          </p>
          <p className="text-sm mt-0.5" style={{ color: "#6b7280" }}>
            Paste a match ID from op.gg or the League client
          </p>
        </div>
        <span className="text-sm ml-4 flex-shrink-0" style={{ color: "#6b7280" }}>
          {open ? "▲" : "▼"}
        </span>
      </button>

      {open && (
        <div className="px-6 pb-6 border-t" style={{ borderColor: "rgba(80,90,180,0.2)" }}>
          <div className="pt-5">
            <MatchHistoryForm />
          </div>
        </div>
      )}
    </div>
  );
}
