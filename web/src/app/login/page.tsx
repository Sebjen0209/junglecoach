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
    <div className="w-full max-w-sm">
      <div className="bg-[#0E0E18] border border-[#1C1C2A] rounded-2xl p-8 shadow-[0_24px_64px_rgba(0,0,0,0.5)]">
        <h1 className="text-xl font-bold text-white mb-1">Welcome back</h1>
        <p className="text-sm text-[#8080A0] mb-5">Log in to your account</p>

        <div className="bg-[#00e5ff]/5 border border-[#00e5ff]/15 rounded-lg px-4 py-3 mb-6">
          <p className="text-xs text-[#8080A0] leading-relaxed">
            <span className="text-[#00e5ff] font-medium">Tip:</span> Log in via the app — the overlay&apos;s login button opens this page automatically.
          </p>
        </div>

        {(error || urlError) && (
          <div className="bg-[#E24B4A]/10 border border-[#E24B4A]/20 text-[#E24B4A] text-sm px-4 py-3 rounded-lg mb-5">
            {error ?? (urlReason ?? "Authentication failed. Please try again.")}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-[#8080A0] mb-1.5 uppercase tracking-wider">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="input-base"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-[#8080A0] mb-1.5 uppercase tracking-wider">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="input-base"
              placeholder="••••••••"
            />
          </div>

          <button type="submit" disabled={loading} className="btn-primary w-full py-2.5 mt-1">
            {loading ? "Logging in…" : "Log in"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-[#8080A0]">
          Don&apos;t have an account?{" "}
          <Link href="/signup" className="text-[#E24B4A] hover:text-[#d03d3c] transition-colors">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 bg-[#07070D]">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[300px] bg-[#E24B4A]/4 blur-[120px] rounded-full" />
      </div>
      <Link href="/" className="text-xl font-bold text-white mb-10 tracking-tight relative">
        JungleCoach<span className="text-[#E24B4A]">.</span>
      </Link>
      <Suspense>
        <LoginForm />
      </Suspense>
    </div>
  );
}
