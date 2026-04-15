"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase";

export default function SignupPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const plan = searchParams.get("plan");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const supabase = createClient();
    const redirectTo = `${window.location.origin}/api/auth/callback${plan ? `?plan=${plan}` : ""}`;

    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: { emailRedirectTo: redirectTo },
    });

    if (error) {
      setError(error.message);
      setLoading(false);
      return;
    }

    setDone(true);
  }

  if (done) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-4">
        <Link href="/" className="text-xl font-bold text-white mb-10">
          JungleCoach<span className="text-[#E24B4A]">.</span>
        </Link>
        <div className="w-full max-w-sm bg-[#13131A] border border-[#1E1E2A] rounded-xl p-8 text-center">
          <div className="text-3xl mb-4">📧</div>
          <h2 className="text-lg font-bold text-white mb-2">Check your email</h2>
          <p className="text-sm text-[#555]">
            We&apos;ve sent a confirmation link to{" "}
            <span className="text-white">{email}</span>. Click it to activate
            your account.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <Link
        href="/"
        className="text-xl font-bold text-white mb-10 tracking-tight"
      >
        JungleCoach<span className="text-[#E24B4A]">.</span>
      </Link>

      <div className="w-full max-w-sm bg-[#13131A] border border-[#1E1E2A] rounded-xl p-8">
        <h1 className="text-xl font-bold text-white mb-1">Create account</h1>
        <p className="text-sm text-[#555] mb-6">
          {plan ? `Sign up and activate your ${plan.replace("_", " ")} plan` : "Start for free today"}
        </p>

        {error && (
          <div className="bg-[#E24B4A]/10 border border-[#E24B4A]/20 text-[#E24B4A] text-sm px-4 py-3 rounded-lg mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-[#888] mb-1.5">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="w-full bg-[#0A0A0F] border border-[#1E1E2A] rounded-lg px-3 py-2.5 text-sm text-white placeholder:text-[#333] focus:outline-none focus:border-[#E24B4A]/50 transition-colors"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-[#888] mb-1.5">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
              className="w-full bg-[#0A0A0F] border border-[#1E1E2A] rounded-lg px-3 py-2.5 text-sm text-white placeholder:text-[#333] focus:outline-none focus:border-[#E24B4A]/50 transition-colors"
              placeholder="Min. 8 characters"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[#E24B4A] hover:bg-[#d03d3c] disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded-lg text-sm transition-colors"
          >
            {loading ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-[#555]">
          Already have an account?{" "}
          <Link href="/login" className="text-[#E24B4A] hover:underline">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
