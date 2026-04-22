"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/dashboard/history", label: "History" },
  { href: "/billing", label: "Billing" },
  { href: "/settings", label: "Settings" },
];

interface AppShellProps {
  user: { email?: string };
  children: React.ReactNode;
}

export function AppShell({ user, children }: AppShellProps) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "#080818" }}>

      {/* Aurora layer */}
      <div className="fixed inset-0 pointer-events-none z-0" aria-hidden>
        {/* Deep indigo base */}
        <div style={{ position: "absolute", inset: 0, background: "#080818" }} />
        {/* Teal top-left bloom */}
        <div style={{
          position: "absolute", inset: 0,
          background: "radial-gradient(ellipse 80% 55% at 0% 0%, rgba(0,60,120,0.45) 0%, transparent 65%)",
        }} />
        {/* Violet bottom-right bloom */}
        <div style={{
          position: "absolute", inset: 0,
          background: "radial-gradient(ellipse 70% 60% at 100% 100%, rgba(60,10,100,0.4) 0%, transparent 65%)",
        }} />
        {/* Subtle cyan midpoint */}
        <div style={{
          position: "absolute", inset: 0,
          background: "radial-gradient(ellipse 50% 40% at 60% 40%, rgba(0,229,255,0.04) 0%, transparent 70%)",
        }} />
      </div>

      {/* Nav — identical structure to landing page Nav */}
      <nav className="sticky top-0 z-50 px-6 py-4 transition-all duration-300 border-b border-[#1a1a4a] bg-[#080818]/90 backdrop-blur-2xl">
        <div className="max-w-7xl mx-auto grid grid-cols-3 items-center">
          {/* Left — logo */}
          <Link
            href="/"
            className="arcane-heading text-lg font-bold tracking-wider justify-self-start"
            style={{ color: "#f0c040", textShadow: "0 0 20px rgba(240,192,64,0.5)" }}
          >
            JungleCoach
          </Link>

          {/* Centre — nav links */}
          <div className="hidden md:flex items-center justify-center gap-8">
            {NAV_LINKS.map((link) => {
              const isActive = pathname === link.href ||
                (link.href !== "/dashboard" && pathname.startsWith(link.href));
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className="sub-heading text-xs tracking-widest transition-colors hover:text-white"
                  style={{ color: isActive ? "#00e5ff" : "#f0f2ff" }}
                >
                  {link.label}
                </Link>
              );
            })}
          </div>

          {/* Right — sign out */}
          <div className="flex items-center justify-end gap-3">
            <form action="/api/auth/signout" method="POST">
              <button
                type="submit"
                className="sub-heading text-xs text-[#c5cae9] hover:text-white transition-colors tracking-widest py-3"
              >
                Sign out
              </button>
            </form>
          </div>
        </div>
      </nav>

      <main className="relative z-10 flex-1 px-6 py-10 max-w-7xl mx-auto w-full">
        {children}
      </main>
    </div>
  );
}
