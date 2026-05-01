import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase-server";
import { AppShell } from "@/components/AppShell";

export default async function SettingsPage() {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const initial = (user.email ?? "?")[0].toUpperCase();
  const memberSince = new Date(user.created_at).toLocaleDateString("en-GB", {
    day: "numeric", month: "long", year: "numeric",
  });

  return (
    <AppShell user={user}>
      <div className="max-w-xl space-y-4">

          {/* Profile card */}
          <div
            className="rounded-2xl border overflow-hidden"
            style={{
              background: "rgba(20,20,60,0.75)",
              borderColor: "rgba(80,90,180,0.35)",
              backdropFilter: "blur(16px)",
            }}
          >
            {/* Banner */}
            <div
              className="h-24 w-full"
              style={{
                background: "linear-gradient(135deg, rgba(0,60,120,0.8) 0%, rgba(60,10,100,0.7) 50%, rgba(0,229,255,0.15) 100%)",
              }}
            />

            {/* Avatar + name */}
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
