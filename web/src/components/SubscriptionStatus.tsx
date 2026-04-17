interface SubscriptionStatusProps {
  plan: string;
  status: string;
  currentPeriodEnd: string | null;
  cancelAtPeriodEnd?: boolean;
}

const PLAN_LABELS: Record<string, string> = {
  free: "Free",
  premium: "Premium",
  pro: "Pro",
};

const STATUS_STYLES: Record<string, string> = {
  active: "bg-green-500/10 text-green-400 border-green-500/20",
  cancelling: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  cancelled: "bg-[#1E1E2A] text-[#555] border-[#2A2A3A]",
  past_due: "bg-red-500/10 text-red-400 border-red-500/20",
};

export function SubscriptionStatus({
  plan,
  status,
  currentPeriodEnd,
  cancelAtPeriodEnd = false,
}: SubscriptionStatusProps) {
  const label = PLAN_LABELS[plan] ?? plan;
  const effectiveStatus = cancelAtPeriodEnd ? "cancelling" : status;
  const statusStyle = STATUS_STYLES[effectiveStatus] ?? STATUS_STYLES.active;
  const periodDate = currentPeriodEnd
    ? new Date(currentPeriodEnd).toLocaleDateString("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <span className="text-lg font-bold text-white">{label}</span>
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${statusStyle}`}
        >
          {effectiveStatus === "active"
            ? "Active"
            : effectiveStatus === "cancelling"
            ? "Cancels at period end"
            : effectiveStatus === "cancelled"
            ? "Cancelled"
            : "Past Due"}
        </span>
      </div>

      {effectiveStatus === "active" && periodDate && (
        <p className="text-xs text-[#555]">Renews on {periodDate}</p>
      )}

      {effectiveStatus === "cancelling" && periodDate && (
        <p className="text-xs text-yellow-500/70">
          Access until {periodDate} — your subscription will not renew.
        </p>
      )}

      {effectiveStatus === "cancelled" && (
        <p className="text-xs text-[#555]">Your subscription has ended.</p>
      )}

      {status === "past_due" && (
        <p className="text-xs text-red-400/80">
          Payment failed — update your payment method to keep access.
        </p>
      )}
    </div>
  );
}
