import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase-server";
import { SubscriptionStatus } from "@/components/SubscriptionStatus";
import { PLANS } from "@/lib/stripe";
import Link from "next/link";

export default async function BillingPage() {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const { data: subscription } = await supabase
    .from("subscriptions")
    .select("plan, status, current_period_end, stripe_customer_id")
    .eq("user_id", user.id)
    .maybeSingle();

  const plan = subscription?.plan ?? "free";
  const status = subscription?.status ?? "active";
  const periodEnd = subscription?.current_period_end ?? null;
  const isPremium = plan !== "free";

  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Billing</h1>
        <p className="text-sm text-[#555] mt-1">
          Manage your subscription and payment details
        </p>
      </div>

      {/* Current plan */}
      <div className="bg-[#13131A] border border-[#1E1E2A] rounded-xl p-6">
        <h2 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-4">
          Current plan
        </h2>
        <SubscriptionStatus
          plan={plan}
          status={status}
          currentPeriodEnd={periodEnd}
        />

        {isPremium && (
          <form action="/api/stripe/portal" method="POST" className="mt-4">
            <button
              type="submit"
              className="text-sm text-[#888] hover:text-white border border-[#1E1E2A] hover:border-[#2A2A3A] px-4 py-2 rounded-lg transition-colors"
            >
              Manage subscription →
            </button>
          </form>
        )}
      </div>

      {/* Upgrade options (shown only for free users) */}
      {!isPremium && (
        <div>
          <h2 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-4">
            Upgrade
          </h2>
          <div className="grid sm:grid-cols-2 gap-4">
            {(
              [
                { key: "premium_monthly", plan: PLANS.premium_monthly },
                { key: "premium_annual", plan: PLANS.premium_annual },
                { key: "pro_monthly", plan: PLANS.pro_monthly },
              ] as const
            ).map(({ key, plan: p }) => (
              <div
                key={key}
                className="bg-[#13131A] border border-[#1E1E2A] rounded-xl p-6"
              >
                <div className="flex items-baseline gap-1 mb-1">
                  <span className="text-2xl font-bold text-white">
                    €{p.price}
                  </span>
                  <span className="text-sm text-[#555]">/{p.interval}</span>
                </div>
                <p className="text-sm font-semibold text-white mb-4">
                  {p.name}
                </p>
                <ul className="space-y-2 mb-6">
                  {p.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-xs text-[#666]">
                      <span className="text-[#E24B4A] shrink-0">✓</span>
                      {f}
                    </li>
                  ))}
                </ul>
                <CheckoutButton planKey={key} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function CheckoutButton({ planKey }: { planKey: string }) {
  return (
    <form action="/api/stripe/checkout" method="POST">
      <input type="hidden" name="plan" value={planKey} />
      <button
        type="submit"
        className="w-full bg-[#E24B4A] hover:bg-[#d03d3c] text-white text-sm font-semibold py-2.5 rounded-lg transition-colors"
      >
        Subscribe
      </button>
    </form>
  );
}
