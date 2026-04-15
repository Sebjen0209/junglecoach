import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase-server";
import Link from "next/link";

export default async function SettingsPage() {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Account settings</h1>
        <p className="text-sm text-[#555] mt-1">Manage your account details</p>
      </div>

      {/* Account info */}
      <div className="bg-[#13131A] border border-[#1E1E2A] rounded-xl divide-y divide-[#1E1E2A]">
        <div className="p-6">
          <h2 className="text-sm font-semibold text-white mb-4">Account</h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-[#555]">Email</span>
              <span className="text-sm text-white">{user.email}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-[#555]">User ID</span>
              <span className="text-xs text-[#444] font-mono">{user.id}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-[#555]">Member since</span>
              <span className="text-sm text-[#888]">
                {new Date(user.created_at).toLocaleDateString("en-GB", {
                  day: "numeric",
                  month: "long",
                  year: "numeric",
                })}
              </span>
            </div>
          </div>
        </div>

        <div className="p-6">
          <h2 className="text-sm font-semibold text-white mb-4">
            Change password
          </h2>
          <ChangePasswordForm />
        </div>
      </div>

      {/* Danger zone */}
      <div className="bg-[#13131A] border border-red-900/20 rounded-xl p-6">
        <h2 className="text-sm font-semibold text-red-400 mb-2">
          Danger zone
        </h2>
        <p className="text-xs text-[#555] mb-4">
          Deleting your account is permanent and cannot be undone. All your data
          will be removed.
        </p>
        <button
          disabled
          className="text-sm text-red-500 border border-red-900/30 px-4 py-2 rounded-lg opacity-50 cursor-not-allowed"
        >
          Delete account
        </button>
      </div>
    </div>
  );
}

function ChangePasswordForm() {
  return (
    <form className="space-y-3">
      <div>
        <label className="block text-xs text-[#555] mb-1.5">
          New password
        </label>
        <input
          type="password"
          name="password"
          minLength={8}
          className="w-full bg-[#0A0A0F] border border-[#1E1E2A] rounded-lg px-3 py-2.5 text-sm text-white placeholder:text-[#333] focus:outline-none focus:border-[#E24B4A]/50 transition-colors"
          placeholder="Min. 8 characters"
        />
      </div>
      <button
        type="button"
        disabled
        className="text-sm bg-[#1E1E2A] text-[#555] px-4 py-2 rounded-lg cursor-not-allowed"
      >
        Update password
      </button>
      <p className="text-xs text-[#444]">
        Password updates handled via email link — coming soon.
      </p>
    </form>
  );
}
