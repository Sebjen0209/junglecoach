import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "JungleCoach — Real-time LoL Gank Assistant",
  description:
    "AI-powered gank priority suggestions for League of Legends junglers. Know where to gank before you even look at the map.",
  keywords: ["League of Legends", "jungler", "gank", "overlay", "AI"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#0A0A0F] text-[#E5E5E5] antialiased">
        {children}
      </body>
    </html>
  );
}
