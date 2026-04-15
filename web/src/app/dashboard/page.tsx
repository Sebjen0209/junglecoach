import { createClient } from "@/lib/supabase-server";
import { SubscriptionStatus } from "@/components/SubscriptionStatus";
import Link from "next/link";

const DOWNLOAD_STEPS = [
  { n: 1, text: "Download the JungleCoach desktop app" },
  { n: 2, text: "Install and launch it" },
  { n: 3, text: "Log in via the app — it will open this browser window" },
  { n: 4, text: "Open a League of Legends game and press Tab" },
];

export default async function DashboardPage() {
  const supabase = createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { data: subscription } = await supabase
    .from("subscriptions")
    .select("plan, status, current_period_end")
    .eq("user_id", user!.id)
    .maybeSingle();

  const plan = subscription?.plan ?? "free";
  const status = subscription?.status ?? "active";
  const periodEnd = subscription?.current_period_end ?? null;
  const isPremium = plan !== "free";

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-sm text-[#555] mt-1">
          Welcome back, {user?.email}
        </p>
      </div>

      {/* Plan banner */}
      <div className="bg-[#13131A] border border-[#1E1E2A] rounded-xl p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <p className="text-xs text-[#555] font-medium uppercase tracking-widest mb-2">
            Current plan
          </p>
          <SubscriptionStatus
            plan={plan}
            status={status}
            currentPeriodEnd={periodEnd}
          />
        </div>
        {!isPremium && (
          <Link
            href="/billing"
            className="shrink-0 bg-[#E24B4A] hover:bg-[#d03d3c] text-white text-sm font-semibold px-5 py-2.5 rounded-lg transition-colors"
          >
            Upgrade to Premium
          </Link>
        )}
      </div>

      {/* Get started */}
      <div className="bg-[#13131A] border border-[#1E1E2A] rounded-xl p-6">
        <h2 className="text-base font-bold text-white mb-4">
          Get started in 4 steps
        </h2>
        <ol className="space-y-3">
          {DOWNLOAD_STEPS.map((step) => (
            <li key={step.n} className="flex items-start gap-3">
              <span className="shrink-0 w-6 h-6 rounded-full bg-[#E24B4A]/10 border border-[#E24B4A]/20 text-[#E24B4A] text-xs font-bold flex items-center justify-center">
                {step.n}
              </span>
              <span className="text-sm text-[#888] pt-0.5">{step.text}</span>
            </li>
          ))}
        </ol>
        <a
          href="#"
          className="inline-flex items-center gap-2 mt-6 bg-[#1E1E2A] hover:bg-[#2A2A3A] text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors"
        >
          ⬇ Download for Windows
        </a>
      </div>

      {/* Usage stats placeholder */}
      <div className="grid sm:grid-cols-3 gap-4">
        {[
          { label: "Games analysed", value: "0" },
          { label: "Gank suggestions", value: "0" },
          { label: "Overlay opens", value: "0" },
        ].map((stat) => (
          <div
            key={stat.label}
            className="bg-[#13131A] border border-[#1E1E2A] rounded-xl p-6"
          >
            <p className="text-3xl font-bold text-white mb-1">{stat.value}</p>
            <p className="text-xs text-[#555]">{stat.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
