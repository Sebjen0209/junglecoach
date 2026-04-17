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
          className={`w-7 h-7 rounded-full border flex items-center justify-center shrink-0 text-[10px] font-bold z-10 ${
            good
              ? "bg-green-500/10 border-green-500/25 text-green-400"
              : "bg-[#E24B4A]/10 border-[#E24B4A]/25 text-[#E24B4A]"
          }`}
        >
          {index + 1}
        </div>
        <div className="w-px flex-1 bg-[#1C1C2A] mt-1" />
      </div>

      {/* Content */}
      <div className="pb-6 flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-2.5">
          <span className="text-xs font-mono text-[#46465C] bg-[#0E0E18] border border-[#1C1C2A] px-2 py-0.5 rounded">
            {moment.timestamp_str}
          </span>
          <span
            className={`text-[10px] font-bold px-2 py-0.5 rounded tracking-wide ${
              good
                ? "text-green-400 bg-green-500/10"
                : "text-[#E24B4A] bg-[#E24B4A]/10"
            }`}
          >
            {good ? "GOOD DECISION" : "MISSED OPPORTUNITY"}
          </span>
        </div>

        <p className="text-sm text-white font-medium mb-1.5">{moment.what_happened}</p>
        <p className="text-sm text-[#8080A0] leading-relaxed">{moment.reasoning}</p>

        {moment.suggestion && (
          <div className="flex gap-3 mt-3 bg-[#0E0E18] border border-[#1C1C2A] rounded-lg p-3.5">
            <span className="text-amber-400 text-sm shrink-0 mt-0.5">→</span>
            <p className="text-sm text-[#8080A0] leading-relaxed">{moment.suggestion}</p>
          </div>
        )}
      </div>
    </div>
  );
}
