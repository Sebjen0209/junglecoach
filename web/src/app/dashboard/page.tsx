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
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-sm text-[#8080A0] mt-1">
          Welcome back, {user?.email}
        </p>
      </div>

      {/* Plan banner */}
      <div className="bg-[#0E0E18] border border-[#1C1C2A] rounded-xl p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <p className="text-[10px] text-[#46465C] font-bold uppercase tracking-[0.15em] mb-3">
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
      <div className="bg-[#0E0E18] border border-[#1C1C2A] rounded-xl p-6">
        <h2 className="text-sm font-bold text-white mb-5 uppercase tracking-wider">
          Get started in 4 steps
        </h2>
        <ol className="space-y-4">
          {DOWNLOAD_STEPS.map((step) => (
            <li key={step.n} className="flex items-start gap-4">
              <span className="shrink-0 w-6 h-6 rounded-full bg-[#E24B4A]/10 border border-[#E24B4A]/20 text-[#E24B4A] text-[10px] font-bold flex items-center justify-center mt-0.5">
                {step.n}
              </span>
              <span className="text-sm text-[#8080A0] leading-relaxed">{step.text}</span>
            </li>
          ))}
        </ol>
        <a
          href="#"
          className="inline-flex items-center gap-2 mt-6 bg-[#141422] hover:bg-[#1C1C2E] border border-[#1C1C2A] hover:border-[#2A2A3A] text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors"
        >
          ⬇ Download for Windows
        </a>
      </div>
    </div>
  );
}
