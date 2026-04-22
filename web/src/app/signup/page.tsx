"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase";

function SignupForm() {
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
      <div className="w-full max-w-sm bg-[#0E0E18] border border-[#1C1C2A] rounded-2xl p-8 text-center shadow-[0_24px_64px_rgba(0,0,0,0.5)]">
        <div className="w-12 h-12 rounded-full bg-[#E24B4A]/10 border border-[#E24B4A]/20 flex items-center justify-center mx-auto mb-4">
          <span className="text-xl">📧</span>
        </div>
        <h2 className="text-lg font-bold text-white mb-2">Check your email</h2>
        <p className="text-sm text-[#8080A0] leading-relaxed">
          We&apos;ve sent a confirmation link to{" "}
          <span className="text-white font-medium">{email}</span>.
          Click here to activate your account.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-sm">
      <div className="bg-[#0E0E18] border border-[#1C1C2A] rounded-2xl p-8 shadow-[0_24px_64px_rgba(0,0,0,0.5)]">
        <h1 className="text-xl font-bold text-white mb-1">Create account</h1>
        <p className="text-sm text-[#8080A0] mb-7">
          {plan ? `Sign up and activate your ${plan.replace("_", " ")} plan` : "Start for free today"}
        </p>

        {error && (
          <div className="bg-[#E24B4A]/10 border border-[#E24B4A]/20 text-[#E24B4A] text-sm px-4 py-3 rounded-lg mb-5">
            {error}
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
              minLength={8}
              autoComplete="new-password"
              className="input-base"
              placeholder="Min. 8 characters"
            />
          </div>

          <button type="submit" disabled={loading} className="btn-primary w-full py-2.5 mt-1">
            {loading ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-[#8080A0]">
          Already have an account?{" "}
          <Link href="/login" className="text-[#E24B4A] hover:text-[#d03d3c] transition-colors">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 bg-[#07070D]">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[300px] bg-[#E24B4A]/4 blur-[120px] rounded-full" />
      </div>
      <Link href="/" className="text-xl font-bold text-white mb-10 tracking-tight relative">
        JungleCoach<span className="text-[#E24B4A]">.</span>
      </Link>
      <Suspense>
        <SignupForm />
      </Suspense>
    </div>
  );
}
