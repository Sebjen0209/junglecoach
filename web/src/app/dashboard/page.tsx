import { createClient } from "@/lib/supabase-server";
import Link from "next/link";
import type { CoachingMoment } from "@/lib/cloud-api";

const GRADIENT = "linear-gradient(135deg, rgba(0,60,120,0.8) 0%, rgba(60,10,100,0.7) 50%, rgba(0,229,255,0.15) 100%)";

const CARD_STYLE = {
  background: "rgba(20,20,60,0.75)",
  borderColor: "rgba(80,90,180,0.35)",
  backdropFilter: "blur(16px)",
};

export default async function DashboardPage() {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();

  const [
    { data: recentRows },
    { count: totalAnalyses },
    { data: subscription },
  ] = await Promise.all([
    supabase
      .from("post_game_analyses")
      .select("match_id, jungler_champion, analysed_at, moments")
      .eq("user_id", user!.id)
      .order("analysed_at", { ascending: false })
      .limit(3),
    supabase
      .from("post_game_analyses")
      .select("id", { count: "exact", head: true })
      .eq("user_id", user!.id),
    supabase
      .from("subscriptions")
      .select("plan, status")
      .eq("user_id", user!.id)
      .maybeSingle(),
  ]);

  const plan = subscription?.plan ?? "free";
  const isActive = subscription && ["active", "cancelling", "past_due"].includes(subscription.status ?? "");
  const isPremium = plan !== "free" && isActive;

  return (
    <div className="space-y-6 max-w-2xl">

      {/* Welcome */}
      <div>
        <h1 className="arcane-heading text-2xl font-bold mb-1" style={{ color: "#f0f2ff" }}>
          Welcome to JungleCoach
        </h1>
        <p className="text-sm" style={{ color: "#7986cb" }}>{user?.email}</p>
      </div>

      {/* Stats row */}
      <div className="rounded-xl border overflow-hidden" style={CARD_STYLE}>
        <div className="h-1.5 w-full" style={{ background: GRADIENT }} />
        <div className="p-4 grid grid-cols-3 gap-3">
          <StatChip label="Analyses" value={totalAnalyses ?? 0} />
          <StatChip label="Plan" value={isPremium ? plan : "Free"} capitalize />
          <StatChip label="Overlay" value={isPremium ? "5s" : "10s"} unit="refresh" />
        </div>
      </div>

      {/* Recent analyses */}
      {recentRows && recentRows.length > 0 && (
        <div className="rounded-xl border overflow-hidden" style={CARD_STYLE}>
          <div className="h-1.5 w-full" style={{ background: GRADIENT }} />
          <div className="p-5 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold" style={{ color: "#7986cb" }}>Recent analyses</p>
              <Link href="/dashboard/post-analysis" className="text-xs transition-colors hover:text-white" style={{ color: "#7986cb" }}>
                View all →
              </Link>
            </div>
            <div className="space-y-2">
              {recentRows.map((row) => {
                const moments = (row.moments ?? []) as CoachingMoment[];
                const good = moments.filter((m) => m.was_good_decision).length;
                const missed = moments.filter((m) => !m.was_good_decision).length;
                return (
                  <Link
                    key={row.match_id}
                    href={`/dashboard/post-analysis/${encodeURIComponent(row.match_id)}`}
                    className="history-card flex items-center justify-between px-4 py-3 group"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className="w-8 h-8 rounded-lg flex items-center justify-center text-[10px] font-bold border shrink-0"
                        style={{ background: "rgba(0,229,255,0.06)", borderColor: "rgba(0,229,255,0.15)", color: "#00e5ff" }}
                      >
                        JG
                      </div>
                      <div>
                        <p className="text-sm font-medium" style={{ color: "#f0f2ff" }}>{row.jungler_champion ?? "Unknown"}</p>
                        <p className="text-xs font-mono" style={{ color: "#46465C" }}>{row.match_id}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 text-xs">
                      <span className="flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                        <span style={{ color: "#4ade80" }}>{good}</span>
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#E24B4A]" />
                        <span style={{ color: "#E24B4A" }}>{missed}</span>
                      </span>
                      <span className="history-arrow transition-colors" style={{ color: "#46465C" }}>→</span>
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Upgrade prompt */}
      {!isPremium && (
        <Link
          href="/account"
          className="rounded-2xl border px-6 py-4 flex items-center gap-4 group transition-all duration-200"
          style={{
            background: "rgba(240,192,64,0.05)",
            borderColor: "rgba(240,192,64,0.2)",
            backdropFilter: "blur(16px)",
          }}
        >
          <div className="flex-1">
            <p className="text-sm font-semibold mb-0.5" style={{ color: "#f0c040" }}>Upgrade to Premium</p>
            <p className="text-sm" style={{ color: "#7986cb" }}>Full speed overlay, post-game analysis, and more</p>
          </div>
          <span className="transition-transform duration-200 group-hover:translate-x-1" style={{ color: "#f0c040" }}>→</span>
        </Link>
      )}

      {/* Quick links */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-2xl border overflow-hidden" style={CARD_STYLE}>
          <div className="h-1.5 w-full" style={{ background: GRADIENT }} />
          <Link
            href="/download"
            className="px-5 py-4 flex items-center gap-4 group transition-all duration-200 hover:bg-white/[0.02]"
          >
            <span className="text-xl">⬇</span>
            <div>
              <p className="text-sm font-semibold" style={{ color: "#f0f2ff" }}>Download</p>
              <p className="text-xs" style={{ color: "#7986cb" }}>Get the desktop app</p>
            </div>
          </Link>
        </div>

        <div
          className="rounded-2xl border overflow-hidden"
          style={{
            background: "rgba(88,101,242,0.07)",
            borderColor: "rgba(88,101,242,0.25)",
            backdropFilter: "blur(16px)",
          }}
        >
          <div className="h-1.5 w-full" style={{ background: GRADIENT }} />
          <a
            href="https://discord.gg/jS2h2mTPna"
            target="_blank"
            rel="noopener noreferrer"
            className="px-5 py-4 flex items-center gap-4 group transition-all duration-200 hover:bg-white/[0.02]"
          >
            <svg width="20" height="20" viewBox="0 0 127.14 96.36" fill="#5865F2" xmlns="http://www.w3.org/2000/svg" className="shrink-0">
              <path d="M107.7,8.07A105.15,105.15,0,0,0,81.47,0a72.06,72.06,0,0,0-3.36,6.83A97.68,97.68,0,0,0,49,6.83,72.37,72.37,0,0,0,45.64,0,105.89,105.89,0,0,0,19.39,8.09C2.79,32.65-1.71,56.6.54,80.21h0A105.73,105.73,0,0,0,32.71,96.36,77.7,77.7,0,0,0,39.6,85.25a68.42,68.42,0,0,1-10.85-5.18c.91-.66,1.8-1.34,2.66-2a75.57,75.57,0,0,0,64.32,0c.87.71,1.76,1.39,2.66,2a68.68,68.68,0,0,1-10.87,5.19,77,77,0,0,0,6.89,11.1A105.25,105.25,0,0,0,126.6,80.22h0C129.24,52.84,122.09,29.11,107.7,8.07ZM42.45,65.69C36.18,65.69,31,60,31,53s5-12.74,11.43-12.74S54,46,53.89,53,48.84,65.69,42.45,65.69Zm42.24,0C78.41,65.69,73.25,60,73.25,53s5-12.74,11.44-12.74S96.23,46,96.12,53,91.08,65.69,84.69,65.69Z" />
            </svg>
            <div>
              <p className="text-sm font-semibold" style={{ color: "#f0f2ff" }}>Discord</p>
              <p className="text-xs" style={{ color: "#7986cb" }}>Join our community</p>
            </div>
          </a>
        </div>
      </div>

    </div>
  );
}

function StatChip({ label, value, unit, capitalize }: { label: string; value: string | number; unit?: string; capitalize?: boolean }) {
  return (
    <div
      className="rounded-xl p-4 border text-center"
      style={{ background: "rgba(13,13,43,0.6)", borderColor: "rgba(80,90,180,0.25)", backdropFilter: "blur(16px)" }}
    >
      <p
        className="text-xl font-bold arcane-heading"
        style={{ color: "#f0f2ff", textTransform: capitalize ? "capitalize" : undefined }}
      >
        {value}
        {unit && <span className="text-xs font-normal ml-1" style={{ color: "#7986cb" }}>{unit}</span>}
      </p>
      <p className="text-xs mt-1" style={{ color: "#7986cb" }}>{label}</p>
    </div>
  );
}
