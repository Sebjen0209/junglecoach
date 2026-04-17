import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase-server";
import { SubscriptionStatus } from "@/components/SubscriptionStatus";
import { AppShell } from "@/components/AppShell";
import { PLANS } from "@/lib/stripe";

interface PageProps {
  searchParams: { success?: string; cancelled?: string };
}

const PAID_PLANS = [
  { key: "premium_monthly" as const, plan: PLANS.premium_monthly },
  { key: "premium_annual" as const, plan: PLANS.premium_annual },
  { key: "pro_monthly" as const, plan: PLANS.pro_monthly },
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
          <h1 className="text-2xl font-bold text-white">Billing</h1>
          <p className="text-sm text-[#8080A0] mt-1">
            Manage your subscription and payment details
          </p>
        </div>

        {searchParams.success && (
          <div className="bg-green-500/10 border border-green-500/20 text-green-400 rounded-xl px-5 py-4 text-sm font-medium">
            🎉 Subscription activated — welcome aboard!
          </div>
        )}
        {searchParams.cancelled && (
          <div className="bg-[#1C1C2A] border border-[#2A2A3A] text-[#8080A0] rounded-xl px-5 py-4 text-sm">
            Checkout cancelled — no charge was made.
          </div>
        )}

        {/* Current plan */}
        <div className="bg-[#0E0E18] border border-[#1C1C2A] rounded-xl p-6">
          <p className="text-[10px] font-bold text-[#46465C] uppercase tracking-[0.15em] mb-4">
            Current plan
          </p>
          <SubscriptionStatus
            plan={plan}
            status={status}
            currentPeriodEnd={periodEnd}
            cancelAtPeriodEnd={cancelAtPeriodEnd}
          />

          {isActive && (
            <div className="mt-6 pt-5 border-t border-[#1C1C2A] flex flex-col sm:flex-row sm:items-center gap-3">
              {cancelAtPeriodEnd ? (
                <form action="/api/stripe/portal" method="POST">
                  <button
                    type="submit"
                    className="text-sm text-green-400 hover:text-green-300 transition-colors"
                  >
                    Reactivate subscription →
                  </button>
                </form>
              ) : (
                <>
                  <form action="/api/stripe/portal" method="POST">
                    <button
                      type="submit"
                      className="text-sm bg-[#141422] hover:bg-[#1C1C2E] border border-[#1C1C2A] hover:border-[#2A2A3A] text-white px-4 py-2 rounded-lg transition-colors"
                    >
                      Update payment method →
                    </button>
                  </form>
                  <form action="/api/stripe/portal" method="POST">
                    <button
                      type="submit"
                      className="text-sm text-[#46465C] hover:text-red-400 transition-colors"
                    >
                      Cancel subscription
                    </button>
                  </form>
                </>
              )}
            </div>
          )}

          {isActive && cancelAtPeriodEnd && (
            <p className="text-xs text-[#46465C] mt-3">
              To switch plans, let your subscription expire then pick a new one.
            </p>
          )}
        </div>

        {/* Plan selection — only for free or fully cancelled */}
        {!isActive && (
          <div>
            <p className="text-[10px] font-bold text-[#46465C] uppercase tracking-[0.15em] mb-4">
              {status === "cancelled" ? "Choose a new plan" : "Choose a plan"}
            </p>
            <div className="grid sm:grid-cols-3 gap-3">
              {PAID_PLANS.map(({ key, plan: p }) => (
                <div
                  key={key}
                  className="bg-[#0E0E18] border border-[#1C1C2A] hover:border-[#E24B4A]/25 rounded-xl p-5 transition-colors"
                >
                  <p className="text-[10px] font-bold text-[#8080A0] uppercase tracking-widest mb-3">
                    {p.name}
                  </p>
                  <div className="flex items-baseline gap-1 mb-4">
                    <span className="text-2xl font-bold text-white">€{p.price}</span>
                    <span className="text-xs text-[#46465C]">/{p.interval}</span>
                  </div>
                  <ul className="space-y-1.5 mb-5">
                    {p.features.map((f) => (
                      <li key={f} className="flex items-start gap-2 text-xs text-[#8080A0]">
                        <span className="text-[#E24B4A] shrink-0 mt-0.5">✓</span>
                        {f}
                      </li>
                    ))}
                  </ul>
                  <form action="/api/stripe/checkout" method="POST">
                    <input type="hidden" name="plan" value={key} />
                    <button
                      type="submit"
                      className="w-full bg-[#E24B4A] hover:bg-[#d03d3c] text-white text-sm font-semibold py-2.5 rounded-lg transition-colors"
                    >
                      Subscribe
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
