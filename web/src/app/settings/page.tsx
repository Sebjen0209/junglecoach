import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase-server";
import { AppShell } from "@/components/AppShell";

export default async function SettingsPage() {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  return (
    <AppShell user={user}>
      <div className="max-w-2xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Settings</h1>
          <p className="text-sm text-[#8080A0] mt-1">Manage your account details</p>
        </div>

        {/* Account info */}
        <div className="bg-[#0E0E18] border border-[#1C1C2A] rounded-xl overflow-hidden">
          <div className="px-6 py-5 border-b border-[#1C1C2A]">
            <p className="text-[10px] font-bold text-[#46465C] uppercase tracking-[0.15em] mb-4">Account</p>
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
            <p className="text-[10px] font-bold text-[#46465C] uppercase tracking-[0.15em] mb-4">Password</p>
            <ChangePasswordForm />
          </div>
        </div>

        {/* Danger zone */}
        <div className="bg-[#0E0E18] border border-red-900/20 rounded-xl p-6">
          <p className="text-[10px] font-bold text-red-500/60 uppercase tracking-[0.15em] mb-3">Danger zone</p>
          <p className="text-sm text-[#8080A0] mb-4 leading-relaxed">
            Deleting your account is permanent and cannot be undone. All your data will be removed.
          </p>
          <button
            disabled
            className="text-sm text-red-500/50 border border-red-900/20 px-4 py-2 rounded-lg cursor-not-allowed"
          >
            Delete account
          </button>
        </div>
      </div>
    </AppShell>
  );
}

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-sm text-[#8080A0] shrink-0">{label}</span>
      <span className={`text-sm text-white truncate ${mono ? "font-mono text-xs text-[#46465C]" : ""}`}>
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
          className="text-sm bg-[#141422] border border-[#1C1C2A] text-[#46465C] px-4 py-2 rounded-lg cursor-not-allowed"
        >
          Update password
        </button>
        <p className="text-xs text-[#46465C]">Coming soon</p>
      </div>
    </div>
  );
}
