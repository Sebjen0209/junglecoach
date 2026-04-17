import Link from "next/link";

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
  return (
    <div className="min-h-screen flex flex-col bg-[#07070D]">
      <nav className="border-b border-[#1C1C2A] px-6 bg-[#07070D]/95 backdrop-blur-xl sticky top-0 z-40">
        <div className="max-w-6xl mx-auto flex items-center justify-between h-14">
          <div className="flex items-center gap-6">
            <Link href="/" className="text-sm font-bold text-white tracking-tight">
              JungleCoach<span className="text-[#E24B4A]">.</span>
            </Link>
            <div className="hidden sm:flex items-center">
              {NAV_LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="text-sm text-[#8080A0] hover:text-white px-3 py-1.5 rounded-md hover:bg-[#0E0E18] transition-colors"
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-[#46465C] hidden sm:block truncate max-w-[180px]">
              {user.email}
            </span>
            <div className="w-px h-4 bg-[#1C1C2A] hidden sm:block" />
            <form action="/api/auth/signout" method="POST">
              <button
                type="submit"
                className="text-xs text-[#8080A0] hover:text-white transition-colors"
              >
                Sign out
              </button>
            </form>
          </div>
        </div>
      </nav>

      <main className="flex-1 px-6 py-8 max-w-6xl mx-auto w-full">
        {children}
      </main>
    </div>
  );
}
