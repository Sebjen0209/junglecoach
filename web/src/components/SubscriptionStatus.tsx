interface SubscriptionStatusProps {
  plan: string;
  status: string;
  currentPeriodEnd: string | null;
}

const PLAN_LABELS: Record<string, string> = {
  free: "Free",
  premium: "Premium",
  pro: "Pro",
};

const STATUS_STYLES: Record<string, string> = {
  active: "bg-green-500/10 text-green-400 border-green-500/20",
  cancelled: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  past_due: "bg-red-500/10 text-red-400 border-red-500/20",
};

export function SubscriptionStatus({
  plan,
  status,
  currentPeriodEnd,
}: SubscriptionStatusProps) {
  const label = PLAN_LABELS[plan] ?? plan;
  const statusStyle = STATUS_STYLES[status] ?? STATUS_STYLES.active;

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm font-medium text-white">{label}</span>
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${statusStyle}`}
      >
        {status === "active" ? "Active" : status === "cancelled" ? "Cancelled" : "Past Due"}
      </span>
      {currentPeriodEnd && status !== "cancelled" && (
        <span className="text-xs text-[#555]">
          Renews {new Date(currentPeriodEnd).toLocaleDateString("en-GB")}
        </span>
      )}
    </div>
  );
}
