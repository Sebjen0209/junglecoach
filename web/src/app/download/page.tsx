import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase-server";
import { AppShell } from "@/components/AppShell";

const GRADIENT = "linear-gradient(135deg, rgba(0,60,120,0.8) 0%, rgba(60,10,100,0.7) 50%, rgba(0,229,255,0.15) 100%)";

const STEPS = [
  { n: "01", text: "Download the JungleCoach desktop app using the button below" },
  { n: "02", text: "Install and launch it" },
  { n: "03", text: "Log in with your JungleCoach account — same email and password as this website" },
  { n: "04", text: "Open a League of Legends game — the overlay activates automatically" },
];

export default async function DownloadPage() {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <AppShell user={user}>
      <div className="max-w-xl space-y-6">

        <div>
          <h1 className="arcane-heading text-2xl font-bold" style={{ color: "#f0f2ff" }}>Download</h1>
          <p className="text-sm mt-1" style={{ color: "#c5cae9" }}>Get the JungleCoach desktop app for Windows</p>
        </div>

        {/* Download button */}
        <div
          className="rounded-2xl border overflow-hidden"
          style={{
            background: "rgba(240,192,64,0.07)",
            borderColor: "rgba(240,192,64,0.3)",
            backdropFilter: "blur(16px)",
            boxShadow: "0 0 40px rgba(240,192,64,0.06)",
          }}
        >
          <div className="h-1.5 w-full" style={{ background: GRADIENT }} />
          <a
            href="https://github.com/Sebjen0209/junglecoach/releases/latest/download/JungleCoach-Setup.exe"
            download
            className="px-6 py-5 flex items-center gap-5 group transition-all duration-200 hover:bg-white/[0.02]"
          >
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 text-xl"
              style={{ background: "rgba(240,192,64,0.1)", border: "1px solid rgba(240,192,64,0.25)" }}
            >
              ⬇
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold mb-0.5" style={{ color: "#f0c040" }}>JungleCoach for Windows</p>
              <p className="text-sm" style={{ color: "#7986cb" }}>Latest release · click to install</p>
            </div>
            <span className="transition-transform duration-200 group-hover:translate-x-1 text-lg" style={{ color: "#f0c040" }}>↓</span>
          </a>
        </div>

        {/* Steps */}
        <div
          className="rounded-2xl border overflow-hidden"
          style={{
            background: "rgba(20,20,60,0.75)",
            borderColor: "rgba(80,90,180,0.35)",
            backdropFilter: "blur(16px)",
          }}
        >
          <div className="h-1.5 w-full" style={{ background: GRADIENT }} />
          <div className="p-6">
            <h2 className="text-sm font-semibold mb-6" style={{ color: "#f0f2ff" }}>Get started in 4 steps</h2>
            <ol className="space-y-5">
              {STEPS.map((step) => (
                <li key={step.n} className="flex items-start gap-4">
                  <span
                    className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold border"
                    style={{
                      background: "rgba(240,192,64,0.08)",
                      borderColor: "rgba(240,192,64,0.25)",
                      color: "#f0c040",
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {step.n}
                  </span>
                  <span className="text-sm leading-relaxed pt-1.5" style={{ color: "#c5cae9" }}>{step.text}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>

        <p className="text-xs" style={{ color: "#46465C" }}>
          Windows only · Mac and Linux support coming soon
        </p>

      </div>
    </AppShell>
  );
}
