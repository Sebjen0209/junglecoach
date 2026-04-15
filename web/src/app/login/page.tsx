"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/dashboard";
  const urlError = searchParams.get("error");
  const urlReason = searchParams.get("reason");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({ email, password });

    if (error) {
      setError(error.message);
      setLoading(false);
      return;
    }

    router.push(next);
    router.refresh();
  }

  return (
    <div className="w-full max-w-sm bg-[#13131A] border border-[#1E1E2A] rounded-xl p-8">
      <h1 className="text-xl font-bold text-white mb-1">Welcome back</h1>
      <p className="text-sm text-[#555] mb-6">Log in to your account</p>

      {(error || urlError) && (
        <div className="bg-[#E24B4A]/10 border border-[#E24B4A]/20 text-[#E24B4A] text-sm px-4 py-3 rounded-lg mb-4">
          {error ?? (urlReason ?? "Authentication failed. Please try again.")}
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
            autoComplete="current-password"
            className="w-full bg-[#0A0A0F] border border-[#1E1E2A] rounded-lg px-3 py-2.5 text-sm text-white placeholder:text-[#333] focus:outline-none focus:border-[#E24B4A]/50 transition-colors"
            placeholder="••••••••"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-[#E24B4A] hover:bg-[#d03d3c] disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded-lg text-sm transition-colors"
        >
          {loading ? "Logging in…" : "Log in"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-[#555]">
        Don&apos;t have an account?{" "}
        <Link href="/signup" className="text-[#E24B4A] hover:underline">
          Sign up
        </Link>
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <Link
        href="/"
        className="text-xl font-bold text-white mb-10 tracking-tight"
      >
        JungleCoach<span className="text-[#E24B4A]">.</span>
      </Link>
      <Suspense>
        <LoginForm />
      </Suspense>
    </div>
  );
}
