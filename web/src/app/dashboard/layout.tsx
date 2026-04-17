import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase-server";
import { AppShell } from "@/components/AppShell";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  return <AppShell user={user}>{children}</AppShell>;
}
