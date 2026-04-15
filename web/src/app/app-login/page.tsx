"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase";

/**
 * The desktop app opens this page in a browser window.
 * After the user logs in, Supabase redirects here via the auth callback.
 * We grab the session token and send it back to the desktop app via deep link.
 */
export default function AppLoginPage() {
  const [status, setStatus] = useState<"loading" | "sending" | "done" | "error">("loading");

  useEffect(() => {
    async function sendToken() {
      const supabase = createClient();
      const {
        data: { session },
        error,
      } = await supabase.auth.getSession();

      if (error || !session) {
        setStatus("error");
        return;
      }

      setStatus("sending");

      // Hand the access token back to the desktop app via deep link
      const deepLink = `junglecoach://auth?token=${encodeURIComponent(session.access_token)}`;
      window.location.href = deepLink;

      setStatus("done");
    }

    void sendToken();
  }, []);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 text-center">
      <span className="text-xl font-bold text-white mb-8">
        JungleCoach<span className="text-[#E24B4A]">.</span>
      </span>

      {status === "loading" && (
        <>
          <div className="w-6 h-6 border-2 border-[#E24B4A] border-t-transparent rounded-full animate-spin mb-4" />
          <p className="text-sm text-[#555]">Verifying your session…</p>
        </>
      )}

      {status === "sending" && (
        <>
          <div className="text-3xl mb-4">🔗</div>
          <p className="text-white font-semibold mb-2">Opening JungleCoach…</p>
          <p className="text-sm text-[#555]">
            You can close this tab once the app opens.
          </p>
        </>
      )}

      {status === "done" && (
        <>
          <div className="text-3xl mb-4">✅</div>
          <p className="text-white font-semibold mb-2">You&apos;re logged in!</p>
          <p className="text-sm text-[#555]">You can close this tab.</p>
        </>
      )}

      {status === "error" && (
        <>
          <div className="text-3xl mb-4">⚠️</div>
          <p className="text-white font-semibold mb-2">Login failed</p>
          <p className="text-sm text-[#555] mb-4">
            Your session could not be verified. Please try again from the app.
          </p>
          <a
            href="/login"
            className="text-sm text-[#E24B4A] hover:underline"
          >
            Go to login
          </a>
        </>
      )}
    </div>
  );
}
