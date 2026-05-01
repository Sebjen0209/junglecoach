import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase-server";
import { SubscriptionStatus } from "@/components/SubscriptionStatus";
import { AppShell } from "@/components/AppShell";
import { PLANS } from "@/lib/stripe";

interface PageProps {
  searchParams: { success?: string; cancelled?: string; error?: string };
}

const ACCENT = {
  gold:    { border: "rgba(240,192,64,0.35)",  glow: "rgba(240,192,64,0.1)",  text: "#f0c040",  bg: "rgba(240,192,64,0.08)"  },
  cyan:    { border: "rgba(0,229,255,0.25)",   glow: "rgba(0,229,255,0.07)",  text: "#00e5ff",  bg: "rgba(0,229,255,0.05)"   },
  magenta: { border: "rgba(200,80,255,0.25)",  glow: "rgba(200,80,255,0.07)", text: "#c850ff",  bg: "rgba(200,80,255,0.05)"  },
};

const PAID_PLANS = [
  {
    key: "premium_monthly" as const,
    plan: PLANS.premium_monthly,
    accent: ACCENT.gold,
    badge: null,
    highlight: true,
    cta: "Start Premium",
    features: [
      "Live overlay at full speed (5s refresh)",
      "Full reasoning with every suggestion",
      "15 post-game analyses / week",
      "Full history dashboard",
      "No ads",
    ],
  },
  {
    key: "premium_annual" as const,
    plan: PLANS.premium_annual,
    accent: ACCENT.cyan,
    badge: "SAVE €36",
    highlight: false,
    cta: "Get annual",
    features: [
      "Everything in Premium",
      "Billed annually — save €36 vs monthly",
    ],
  },
  {
    key: "pro_monthly" as const,
    plan: PLANS.pro_monthly,
    accent: ACCENT.magenta,
    badge: null,
    highlight: false,
    cta: "Go Pro",
    features: [
      "Everything in Premium",
      "35 post-game analyses / week",
      "Priority API queue (faster during peak hours)",
      "No ads",
    ],
  },
];

export default async function AccountPage({ searchParams }: PageProps) {
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

  const initial = (user.email ?? "?")[0].toUpperCase();
  const memberSince = new Date(user.created_at).toLocaleDateString("en-GB", {
    day: "numeric", month: "long", year: "numeric",
  });

  return (
    <AppShell user={user}>
      <div className="max-w-4xl mx-auto space-y-8">

        {/* Profile card */}
        <div
          className="rounded-2xl border overflow-hidden"
          style={{
            background: "rgba(20,20,60,0.75)",
            borderColor: "rgba(80,90,180,0.35)",
            backdropFilter: "blur(16px)",
          }}
        >
          <div
            className="h-24 w-full"
            style={{
              background: "linear-gradient(135deg, rgba(0,60,120,0.8) 0%, rgba(60,10,100,0.7) 50%, rgba(0,229,255,0.15) 100%)",
            }}
          />
          <div className="px-6 pb-6">
            <div className="flex items-end gap-4 -mt-8 mb-5">
              <div
                className="w-16 h-16 rounded-2xl border-2 flex items-center justify-center arcane-heading text-2xl font-bold shrink-0"
                style={{
                  background: "rgba(8,8,24,0.9)",
                  borderColor: "rgba(0,229,255,0.4)",
                  color: "#00e5ff",
                  boxShadow: "0 0 24px rgba(0,229,255,0.15)",
                }}
              >
                {initial}
              </div>
              <div className="pb-1">
                <p className="font-semibold text-sm" style={{ color: "#f0f2ff" }}>{user.email}</p>
                <p className="text-xs mt-0.5" style={{ color: "#7986cb" }}>Member since {memberSince}</p>
              </div>
            </div>
            <div
              className="rounded-xl p-4 space-y-3"
              style={{ background: "rgba(0,0,0,0.2)", border: "1px solid rgba(80,90,180,0.2)" }}
            >
              <Row label="Email" value={user.email ?? "—"} />
              <div className="h-px" style={{ background: "rgba(80,90,180,0.15)" }} />
              <Row label="User ID" value={user.id} mono />
            </div>
          </div>
        </div>

        {/* Billing section */}
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <h2 className="arcane-heading text-lg font-bold" style={{ color: "#f0f2ff" }}>Billing</h2>
            {isActive && (
              <span
                className="text-xs font-semibold px-2.5 py-1 rounded-full capitalize"
                style={{
                  background: "rgba(240,192,64,0.1)",
                  color: "#f0c040",
                  border: "1px solid rgba(240,192,64,0.3)",
                }}
              >
                {plan}
              </span>
            )}
          </div>

          {searchParams.success && (
            <div
              className="rounded-xl px-5 py-4 text-sm font-medium border"
              style={{ background: "rgba(0,229,255,0.06)", borderColor: "rgba(0,229,255,0.25)", color: "#00e5ff" }}
            >
              Subscription activated — welcome aboard!
            </div>
          )}
          {searchParams.cancelled && (
            <div
              className="rounded-xl px-5 py-4 text-sm border"
              style={{ background: "rgba(26,26,74,0.4)", borderColor: "rgba(80,90,180,0.3)", color: "#c5cae9" }}
            >
              Checkout cancelled — no charge was made.
            </div>
          )}
          {searchParams.error === "no_customer" && (
            <div
              className="rounded-xl px-5 py-4 text-sm border"
              style={{ background: "rgba(255,51,102,0.06)", borderColor: "rgba(255,51,102,0.2)", color: "#ff3366" }}
            >
              Could not open billing portal — no payment record found.
            </div>
          )}

          {/* Current plan strip */}
          {isActive && (
            <>
              <div
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-5 py-6 border-y"
                style={{ borderColor: "rgba(80,90,180,0.2)" }}
              >
                <SubscriptionStatus
                  plan={plan}
                  status={status}
                  currentPeriodEnd={periodEnd}
                  cancelAtPeriodEnd={cancelAtPeriodEnd}
                />
                <div className="flex items-center gap-4 shrink-0">
                  {cancelAtPeriodEnd ? (
                    <form action="/api/stripe/portal" method="POST">
                      <button type="submit" className="text-sm font-medium transition-colors" style={{ color: "#00e5ff" }}>
                        Reactivate →
                      </button>
                    </form>
                  ) : (
                    <>
                      <form action="/api/stripe/portal" method="POST">
                        <button type="submit" className="portal-btn btn-arcane-ghost text-sm">
                          Update payment →
                        </button>
                      </form>
                      <form action="/api/stripe/portal" method="POST">
                        <button type="submit" className="cancel-btn text-sm font-medium transition-colors" style={{ color: "#7986cb" }}>
                          Cancel
                        </button>
                      </form>
                    </>
                  )}
                </div>
              </div>
              {cancelAtPeriodEnd && (
                <p className="text-xs" style={{ color: "#7986cb" }}>
                  To switch plans, let your subscription expire then pick a new one.
                </p>
              )}
            </>
          )}

          {/* Plan cards */}
          {!isActive && (
            <div className="space-y-5">
              <p className="text-sm font-medium" style={{ color: "#c5cae9" }}>
                {status === "cancelled" ? "Choose a new plan" : "Upgrade your plan"}
              </p>
              <div className="grid sm:grid-cols-3 gap-4">
                {PAID_PLANS.map(({ key, plan: p, accent, badge, highlight, cta, features }) => (
                  <div
                    key={key}
                    className="plan-card rounded-xl border flex flex-col transition-all duration-300"
                    style={{
                      padding: "1.5rem",
                      background: "rgba(20,20,60,0.75)",
                      borderColor: highlight ? accent.border : "rgba(80,90,180,0.35)",
                      boxShadow: highlight ? `0 0 50px ${accent.glow}` : "none",
                      backdropFilter: "blur(16px)",
                    }}
                  >
                    <div className="mb-5">
                      <div className="flex items-center gap-2 mb-3">
                        <p className="sub-heading text-[10px] font-bold tracking-[0.2em]" style={{ color: accent.text }}>
                          {p.name.toUpperCase()}
                        </p>
                        {badge && (
                          <span
                            className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                            style={{ background: accent.bg, color: accent.text, border: `1px solid ${accent.border}` }}
                          >
                            {badge}
                          </span>
                        )}
                      </div>
                      <div className="flex items-baseline gap-1">
                        <span className="arcane-heading text-3xl font-bold text-[#f0f2ff]">€{p.price}</span>
                        <span className="text-xs text-[#c5cae9]">/ {p.interval}</span>
                      </div>
                    </div>
                    <ul className="space-y-2.5 mb-6 flex-1">
                      {features.map((f) => (
                        <li key={f} className="flex items-start gap-2 text-sm text-[#c5cae9]">
                          <span className="mt-0.5 shrink-0 text-xs" style={{ color: accent.text }}>✦</span>
                          {f}
                        </li>
                      ))}
                    </ul>
                    <form action="/api/stripe/checkout" method="POST">
                      <input type="hidden" name="plan" value={key} />
                      <button
                        type="submit"
                        className="block w-full text-center py-2.5 rounded-lg font-bold text-sm transition-all duration-200"
                        style={{
                          background: highlight ? accent.text : "transparent",
                          color: highlight ? "#080818" : accent.text,
                          border: highlight ? "none" : `1px solid ${accent.border}`,
                        }}
                      >
                        {cta}
                      </button>
                    </form>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

      </div>
    </AppShell>
  );
}

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-6">
      <span className="text-xs shrink-0 pt-0.5" style={{ color: "#7986cb" }}>{label}</span>
      <span
        className="text-right break-all"
        style={{
          color: "#f0f2ff",
          fontFamily: mono ? "monospace" : "inherit",
          fontSize: mono ? "0.68rem" : "0.8rem",
          lineHeight: "1.6",
        }}
      >
        {value}
      </span>
    </div>
  );
}
