import { createClient } from "@/lib/supabase-server";
import { SubscriptionStatus } from "@/components/SubscriptionStatus";
import Link from "next/link";

const DOWNLOAD_STEPS = [
  { n: "01", text: "Download the JungleCoach desktop app" },
  { n: "02", text: "Install and launch it" },
  { n: "03", text: "Log in via the app — it will open this browser window" },
  { n: "04", text: "Open a League of Legends game — the overlay activates automatically" },
];

export default async function DashboardPage() {
  const supabase = createClient();

  const { data: { user } } = await supabase.auth.getUser();

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
        <h1 className="arcane-heading text-2xl font-bold" style={{ color: "#f0f2ff" }}>Dashboard</h1>
        <p className="text-sm mt-1" style={{ color: "#c5cae9" }}>
          Welcome back, {user?.email}
        </p>
      </div>

      {/* Plan banner */}
      <div
        className="rounded-xl p-6 border flex flex-col sm:flex-row sm:items-center justify-between gap-4"
        style={{
          background: "rgba(13,13,43,0.7)",
          borderColor: isPremium ? "rgba(240,192,64,0.25)" : "rgba(26,26,74,0.8)",
          backdropFilter: "blur(16px)",
          boxShadow: isPremium ? "0 0 40px rgba(240,192,64,0.06)" : "none",
        }}
      >
        <div>
          <p className="sub-heading text-[11px] tracking-[0.15em] mb-3" style={{ color: "#c5cae9" }}>
            YOUR PLAN
          </p>
          <SubscriptionStatus plan={plan} status={status} currentPeriodEnd={periodEnd} />
        </div>
        {!isPremium && (
          <Link href="/billing" className="btn-arcane shrink-0 text-xs">
            Upgrade to Premium
          </Link>
        )}
      </div>

      {/* Get started */}
      <div
        className="rounded-xl p-6 border"
        style={{
          background: "rgba(13,13,43,0.7)",
          borderColor: "rgba(26,26,74,0.8)",
          backdropFilter: "blur(16px)",
        }}
      >
        <h2 className="sub-heading text-xs font-bold tracking-[0.2em] mb-6" style={{ color: "#f0f2ff" }}>
          GET STARTED IN 4 STEPS
        </h2>
        <ol className="space-y-5">
          {DOWNLOAD_STEPS.map((step, i) => (
            <li key={step.n} className="flex items-start gap-4">
              <span
                className="sub-heading shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold border"
                style={{
                  background: "rgba(240,192,64,0.08)",
                  borderColor: "rgba(240,192,64,0.25)",
                  color: "#f0c040",
                }}
              >
                {step.n}
              </span>
              <span className="text-sm leading-relaxed pt-1.5" style={{ color: "#c5cae9" }}>{step.text}</span>
            </li>
          ))}
        </ol>
        <a
          href="https://github.com/Sebjen0209/junglecoach/releases/latest/download/JungleCoach-Setup.exe"
          className="inline-flex items-center gap-2 mt-8 btn-arcane-ghost text-xs"
          download
        >
          Download for Windows
        </a>
      </div>
    </div>
  );
}
