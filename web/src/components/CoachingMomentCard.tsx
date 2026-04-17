import type { CoachingMoment } from "@/lib/cloud-api";

interface CoachingMomentCardProps {
  moment: CoachingMoment;
  index: number;
}

export function CoachingMomentCard({ moment, index }: CoachingMomentCardProps) {
  const good = moment.was_good_decision;

  return (
    <div className="relative flex gap-4">
      {/* Timeline spine */}
      <div className="flex flex-col items-center">
        <div
          className={`w-8 h-8 rounded-full border flex items-center justify-center shrink-0 text-xs font-bold z-10 ${
            good
              ? "bg-green-500/10 border-green-500/30 text-green-400"
              : "bg-[#E24B4A]/10 border-[#E24B4A]/30 text-[#E24B4A]"
          }`}
        >
          {index + 1}
        </div>
        <div className="w-px flex-1 bg-[#1E1E2A] mt-1" />
      </div>

      {/* Content */}
      <div className="pb-6 flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-mono text-[#555] bg-[#13131A] border border-[#1E1E2A] px-2 py-0.5 rounded">
            {moment.timestamp_str}
          </span>
          <span
            className={`text-xs font-semibold px-2 py-0.5 rounded ${
              good
                ? "text-green-400 bg-green-500/10"
                : "text-[#E24B4A] bg-[#E24B4A]/10"
            }`}
          >
            {good ? "Good decision" : "Missed opportunity"}
          </span>
        </div>

        <p className="text-sm text-white font-medium mb-1">
          {moment.what_happened}
        </p>
        <p className="text-sm text-[#666] leading-relaxed mb-2">
          {moment.reasoning}
        </p>

        {moment.suggestion && (
          <div className="flex gap-2 mt-2 bg-[#13131A] border border-[#1E1E2A] rounded-lg p-3">
            <span className="text-[#EF9F27] text-sm shrink-0">→</span>
            <p className="text-sm text-[#888]">{moment.suggestion}</p>
          </div>
        )}
      </div>
    </div>
  );
}
