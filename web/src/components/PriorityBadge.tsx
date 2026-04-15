type Priority = "high" | "medium" | "low";

interface PriorityBadgeProps {
  priority: Priority;
}

const BADGE_STYLES: Record<Priority, string> = {
  high: "bg-[#E24B4A]/15 text-[#E24B4A] border border-[#E24B4A]/30",
  medium: "bg-[#EF9F27]/15 text-[#EF9F27] border border-[#EF9F27]/30",
  low: "bg-[#444441]/20 text-[#888884] border border-[#444441]/40",
};

const LABELS: Record<Priority, string> = {
  high: "HIGH",
  medium: "MED",
  low: "LOW",
};

export function PriorityBadge({ priority }: PriorityBadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold tracking-wider ${BADGE_STYLES[priority]}`}
    >
      {LABELS[priority]}
    </span>
  );
}
