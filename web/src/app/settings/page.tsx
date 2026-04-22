import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase-server";
import { AppShell } from "@/components/AppShell";

export default async function SettingsPage() {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <AppShell user={user}>
      <div className="max-w-2xl space-y-6">
        <div>
          <h1 className="arcane-heading text-2xl font-bold" style={{ color: "#f0f2ff" }}>Settings</h1>
          <p className="text-sm mt-1" style={{ color: "#c5cae9" }}>Manage your account details</p>
        </div>

        {/* Account info */}
        <div
          className="rounded-xl border overflow-hidden"
          style={{
            background: "rgba(20,20,60,0.75)",
            borderColor: "rgba(80,90,180,0.35)",
            backdropFilter: "blur(16px)",
          }}
        >
          <div className="px-6 py-5 border-b" style={{ borderColor: "rgba(80,90,180,0.35)" }}>
            <p className="sub-heading text-[10px] font-bold tracking-[0.2em] mb-5" style={{ color: "#7986cb" }}>
              ACCOUNT
            </p>
            <div className="space-y-4">
              <Row label="Email" value={user.email ?? "—"} />
              <Row label="User ID" value={user.id} mono />
              <Row
                label="Member since"
                value={new Date(user.created_at).toLocaleDateString("en-GB", {
                  day: "numeric", month: "long", year: "numeric",
                })}
              />
            </div>
          </div>

          <div className="px-6 py-5">
            <p className="sub-heading text-[10px] font-bold tracking-[0.2em] mb-4" style={{ color: "#7986cb" }}>
              PASSWORD
            </p>
            <ChangePasswordForm />
          </div>
        </div>

        {/* Danger zone */}
        <div
          className="rounded-xl p-6 border"
          style={{
            background: "rgba(13,13,43,0.7)",
            borderColor: "rgba(255,51,102,0.15)",
            backdropFilter: "blur(16px)",
          }}
        >
          <p className="sub-heading text-[10px] font-bold tracking-[0.2em] mb-3" style={{ color: "rgba(255,51,102,0.6)" }}>
            DANGER ZONE
          </p>
          <p className="text-sm leading-relaxed mb-4" style={{ color: "#c5cae9" }}>
            Deleting your account is permanent and cannot be undone. All your data will be removed.
          </p>
          <button
            disabled
            className="sub-heading text-xs tracking-widest px-4 py-2 rounded-lg border cursor-not-allowed opacity-50"
            style={{ color: "#ff3366", borderColor: "rgba(255,51,102,0.2)" }}
          >
            DELETE ACCOUNT
          </button>
        </div>
      </div>
    </AppShell>
  );
}

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-sm shrink-0" style={{ color: "#c5cae9" }}>{label}</span>
      <span
        className="text-sm truncate"
        style={{ color: mono ? "#7986cb" : "#f0f2ff", fontFamily: mono ? "monospace" : "inherit", fontSize: mono ? "0.7rem" : undefined }}
      >
        {value}
      </span>
    </div>
  );
}

function ChangePasswordForm() {
  return (
    <div className="space-y-3">
      <input
        type="password"
        name="password"
        minLength={8}
        disabled
        className="input-base opacity-50 cursor-not-allowed"
        placeholder="Min. 8 characters"
      />
      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled
          className="sub-heading text-xs tracking-widest px-4 py-2 rounded-lg border cursor-not-allowed opacity-50"
          style={{ color: "#c5cae9", borderColor: "rgba(26,26,74,0.8)" }}
        >
          UPDATE PASSWORD
        </button>
        <p className="text-xs" style={{ color: "#7986cb" }}>Coming soon</p>
      </div>
    </div>
  );
}
