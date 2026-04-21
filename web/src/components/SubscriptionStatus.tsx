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

const STATUS_STYLES: Record<string, { bg: string; color: string; border: string; label: string }> = {
  active:     { bg: "rgba(0,229,255,0.08)",  color: "#00e5ff", border: "rgba(0,229,255,0.25)",  label: "Active" },
  cancelling: { bg: "rgba(240,192,64,0.08)", color: "#f0c040", border: "rgba(240,192,64,0.25)", label: "Cancels at period end" },
  cancelled:  { bg: "rgba(26,26,74,0.5)",    color: "#7986cb", border: "rgba(26,26,74,0.8)",    label: "Cancelled" },
  past_due:   { bg: "rgba(255,51,102,0.08)", color: "#ff3366", border: "rgba(255,51,102,0.25)", label: "Past Due" },
};

export function SubscriptionStatus({
  plan,
  status,
  currentPeriodEnd,
  cancelAtPeriodEnd = false,
}: SubscriptionStatusProps) {
  const label = PLAN_LABELS[plan] ?? plan;
  const effectiveStatus = cancelAtPeriodEnd ? "cancelling" : status;
  const s = STATUS_STYLES[effectiveStatus] ?? STATUS_STYLES.active;
  const periodDate = currentPeriodEnd
    ? new Date(currentPeriodEnd).toLocaleDateString("en-GB", {
        day: "numeric", month: "long", year: "numeric",
      })
    : null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <span className="arcane-heading text-xl font-bold" style={{ color: "#f0f2ff" }}>{label}</span>
        <span
          className="sub-heading inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-widest border"
          style={{ background: s.bg, color: s.color, borderColor: s.border }}
        >
          {s.label.toUpperCase()}
        </span>
      </div>

      {effectiveStatus === "active" && periodDate && (
        <p className="text-xs" style={{ color: "#7986cb" }}>Renews on {periodDate}</p>
      )}
      {effectiveStatus === "cancelling" && periodDate && (
        <p className="text-xs" style={{ color: "rgba(240,192,64,0.7)" }}>
          Access until {periodDate} — your subscription will not renew.
        </p>
      )}
      {effectiveStatus === "cancelled" && (
        <p className="text-xs" style={{ color: "#7986cb" }}>Your subscription has ended.</p>
      )}
      {status === "past_due" && (
        <p className="text-xs" style={{ color: "rgba(255,51,102,0.8)" }}>
          Payment failed — update your payment method to keep access.
        </p>
      )}
    </div>
  );
}
