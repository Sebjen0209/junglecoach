import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase-server";
import { SubscriptionStatus } from "@/components/SubscriptionStatus";
import { AppShell } from "@/components/AppShell";
import { PLANS } from "@/lib/stripe";

interface PageProps {
  searchParams: { success?: string; cancelled?: string };
}

const PAID_PLANS = [
  { key: "premium_monthly" as const, plan: PLANS.premium_monthly, color: "#f0c040", border: "rgba(240,192,64,0.3)",  cardCls: "plan-card plan-card-gold",    btnCls: "subscribe-btn-gold",    features: ["Live overlay at full speed (5s refresh)", "Full reasoning with every suggestion", "15 post-game analyses / week", "Full history dashboard", "No ads"] },
  { key: "pro_monthly"     as const, plan: PLANS.pro_monthly,     color: "#c850ff", border: "rgba(200,80,255,0.3)", cardCls: "plan-card plan-card-magenta", btnCls: "subscribe-btn-magenta", features: ["Everything in Premium", "35 post-game analyses / week", "Priority API queue (faster during peak hours)", "No ads"] },
];

export default async function BillingPage({ searchParams }: PageProps) {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: subscription } = await supabase
    .from("subscriptions")
    .select("plan, status, current_period_end, stripe_customer_id, cancel_at_period_end")
    .eq("user_id", user.id)
    .maybeSingle();

  const plan = subscription?.plan ?? "free";
  const status = subscription?.status ?? "active";
  const periodEnd = subscription?.current_period_end ?? null;
  const cancelAtPeriodEnd = subscription?.cancel_at_period_end ?? false;
  const isPremium = plan !== "free";
  const isActive = isPremium && status !== "cancelled";

  return (
    <AppShell user={user}>
      <div className="max-w-3xl space-y-6">
        <div>
          <h1 className="arcane-heading text-2xl font-bold" style={{ color: "#f0f2ff" }}>Billing</h1>
          <p className="text-sm mt-1" style={{ color: "#c5cae9" }}>
            Manage your subscription and payment details
          </p>
        </div>

        {searchParams.success && (
          <div
            className="rounded-xl px-5 py-4 text-sm font-medium border"
            style={{ background: "rgba(0,229,255,0.06)", borderColor: "rgba(0,229,255,0.2)", color: "#00e5ff" }}
          >
            Subscription activated — welcome aboard!
          </div>
        )}
        {searchParams.cancelled && (
          <div
            className="rounded-xl px-5 py-4 text-sm border"
            style={{ background: "rgba(26,26,74,0.5)", borderColor: "rgba(26,26,74,0.8)", color: "#c5cae9" }}
          >
            Checkout cancelled — no charge was made.
          </div>
        )}

        {/* Current plan */}
        <div
          className="rounded-xl p-6 border"
          style={{
            background: "rgba(13,13,43,0.7)",
            borderColor: isActive ? "rgba(240,192,64,0.2)" : "rgba(26,26,74,0.8)",
            backdropFilter: "blur(16px)",
            boxShadow: isActive ? "0 0 40px rgba(240,192,64,0.05)" : "none",
          }}
        >
          <p className="sub-heading text-[10px] tracking-[0.2em] mb-4" style={{ color: "#7986cb" }}>
            CURRENT PLAN
          </p>
          <SubscriptionStatus
            plan={plan}
            status={status}
            currentPeriodEnd={periodEnd}
            cancelAtPeriodEnd={cancelAtPeriodEnd}
          />

          {isActive && (
            <div
              className="mt-6 pt-5 border-t flex flex-col sm:flex-row sm:items-center gap-3"
              style={{ borderColor: "rgba(26,26,74,0.8)" }}
            >
              {cancelAtPeriodEnd ? (
                <form action="/api/stripe/portal" method="POST">
                  <button type="submit" className="text-sm transition-colors" style={{ color: "#00e5ff" }}>
                    Reactivate subscription →
                  </button>
                </form>
              ) : (
                <>
                  <form action="/api/stripe/portal" method="POST">
                    <button type="submit" className="portal-btn btn-arcane-ghost text-xs">
                      Update payment method →
                    </button>
                  </form>
                  <form action="/api/stripe/portal" method="POST">
                    <button
                      type="submit"
                      className="cancel-btn text-sm transition-colors"
                      style={{ color: "#7986cb" }}
                    >
                      Cancel subscription
                    </button>
                  </form>
                </>
              )}
            </div>
          )}

          {isActive && cancelAtPeriodEnd && (
            <p className="text-xs mt-3" style={{ color: "#7986cb" }}>
              To switch plans, let your subscription expire then pick a new one.
            </p>
          )}
        </div>

        {/* Plan selection */}
        {!isActive && (
          <div>
            <p className="sub-heading text-[10px] font-bold tracking-[0.2em] mb-4" style={{ color: "#7986cb" }}>
              {status === "cancelled" ? "CHOOSE A NEW PLAN" : "CHOOSE A PLAN"}
            </p>
            <div className="grid sm:grid-cols-2 gap-4">
              {PAID_PLANS.map(({ key, plan: p, color, border, cardCls, btnCls, features }) => (
                <div
                  key={key}
                  className={`${cardCls} p-5 border flex flex-col`}
                  style={{ borderColor: "rgba(26,26,74,0.8)" }}
                >
                  <p className="sub-heading text-[10px] font-bold tracking-[0.2em] mb-3" style={{ color }}>
                    {p.name.toUpperCase()}
                  </p>
                  <div className="flex items-baseline gap-1 mb-4">
                    <span className="arcane-heading text-2xl font-bold" style={{ color: "#f0f2ff" }}>€{p.price}</span>
                    <span className="text-xs" style={{ color: "#7986cb" }}>/{p.interval}</span>
                  </div>
                  <ul className="space-y-2 mb-5 flex-1">
                    {features.map((f) => (
                      <li key={f} className="flex items-start gap-2 text-xs" style={{ color: "#c5cae9" }}>
                        <span className="shrink-0 mt-0.5" style={{ color }}>✦</span>
                        {f}
                      </li>
                    ))}
                  </ul>
                  <form action="/api/stripe/checkout" method="POST">
                    <input type="hidden" name="plan" value={key} />
                    <button
                      type="submit"
                      className={`${btnCls} w-full py-2.5 rounded-lg sub-heading text-xs font-bold tracking-widest border transition-all duration-200`}
                      style={{ color, borderColor: border, background: "transparent" }}
                    >
                      SUBSCRIBE
                    </button>
                  </form>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
