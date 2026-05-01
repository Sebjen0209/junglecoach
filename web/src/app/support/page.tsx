import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase-server";
import { AppShell } from "@/components/AppShell";

const GRADIENT = "linear-gradient(135deg, rgba(0,60,120,0.8) 0%, rgba(60,10,100,0.7) 50%, rgba(0,229,255,0.15) 100%)";

export default async function SupportPage() {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <AppShell user={user}>
      <div className="max-w-xl space-y-6">

        <div>
          <h1 className="arcane-heading text-2xl font-bold" style={{ color: "#f0f2ff" }}>Support</h1>
          <p className="text-sm mt-1" style={{ color: "#c5cae9" }}>Get help from the JungleCoach team</p>
        </div>

        {/* Discord */}
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
            className="px-6 py-6 flex items-center gap-5 transition-all duration-200 group hover:bg-white/[0.02]"
          >
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: "rgba(88,101,242,0.15)", border: "1px solid rgba(88,101,242,0.3)" }}
            >
              <svg width="22" height="22" viewBox="0 0 127.14 96.36" fill="#5865F2" xmlns="http://www.w3.org/2000/svg">
                <path d="M107.7,8.07A105.15,105.15,0,0,0,81.47,0a72.06,72.06,0,0,0-3.36,6.83A97.68,97.68,0,0,0,49,6.83,72.37,72.37,0,0,0,45.64,0,105.89,105.89,0,0,0,19.39,8.09C2.79,32.65-1.71,56.6.54,80.21h0A105.73,105.73,0,0,0,32.71,96.36,77.7,77.7,0,0,0,39.6,85.25a68.42,68.42,0,0,1-10.85-5.18c.91-.66,1.8-1.34,2.66-2a75.57,75.57,0,0,0,64.32,0c.87.71,1.76,1.39,2.66,2a68.68,68.68,0,0,1-10.87,5.19,77,77,0,0,0,6.89,11.1A105.25,105.25,0,0,0,126.6,80.22h0C129.24,52.84,122.09,29.11,107.7,8.07ZM42.45,65.69C36.18,65.69,31,60,31,53s5-12.74,11.43-12.74S54,46,53.89,53,48.84,65.69,42.45,65.69Zm42.24,0C78.41,65.69,73.25,60,73.25,53s5-12.74,11.44-12.74S96.23,46,96.12,53,91.08,65.69,84.69,65.69Z" />
              </svg>
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold mb-0.5" style={{ color: "#f0f2ff" }}>Join our Discord</p>
              <p className="text-sm" style={{ color: "#7986cb" }}>Ask questions, report bugs, and get help from the team</p>
            </div>
            <span className="text-lg transition-transform duration-200 group-hover:translate-x-1" style={{ color: "#5865F2" }}>→</span>
          </a>
        </div>

      </div>
    </AppShell>
  );
}
