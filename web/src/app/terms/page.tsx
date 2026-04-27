import Link from "next/link";

export const metadata = {
  title: "Terms of Service — JungleCoach",
  description: "Terms of Service for JungleCoach, a real-time League of Legends jungler assistant.",
};

const SECTIONS = [
  {
    id: "acceptance",
    title: "1. Acceptance of Terms",
    body: `By downloading, installing, or using JungleCoach (the "Service"), you agree to be bound by these Terms of Service ("Terms"). If you do not agree, do not use the Service. These Terms apply to all users, including free-tier and paid subscribers.`,
  },
  {
    id: "description",
    title: "2. Description of Service",
    body: `JungleCoach is a desktop application and web platform that provides real-time jungler coaching assistance for League of Legends. It reads publicly available game data from Riot Games' official Live Client Data API (a local service running on your machine during an active game) and generates analytical suggestions to help players improve their decision-making. No game data is transmitted to our servers except champion names and basic game state required to generate AI suggestions.`,
  },
  {
    id: "accounts",
    title: "3. User Accounts",
    body: `You must create an account to access the Service. You are responsible for maintaining the confidentiality of your login credentials and for all activity that occurs under your account. You must provide accurate, current, and complete information when registering. You must be at least 13 years old (or the minimum age required in your country) to use the Service. We reserve the right to suspend or terminate accounts that violate these Terms.`,
  },
  {
    id: "subscriptions",
    title: "4. Subscriptions and Payments",
    body: `JungleCoach offers a free tier and paid subscription plans. Paid plans are billed on a monthly or annual basis via Stripe. By subscribing, you authorise us to charge your payment method on a recurring basis. Subscriptions renew automatically unless cancelled before the renewal date. Refunds are handled at our discretion; please contact support within 7 days of a charge if you believe a billing error has occurred. We reserve the right to change pricing with 30 days' notice. Price changes will not affect your current billing period.`,
  },
  {
    id: "riot-disclaimer",
    title: "5. Riot Games Disclaimer",
    body: `JungleCoach isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games and all associated properties are trademarks or registered trademarks of Riot Games, Inc.

JungleCoach uses Riot Games' official Live Client Data API, which is explicitly provided by Riot for use by third-party developers. The Service reads only data that is directly visible to the player and does not access hidden game state, fog-of-war information, or any data not permitted under Riot's API Terms of Service and General Policies.

JungleCoach is registered on the Riot Developer Portal as required. We comply with Riot's policies, including the requirement that a free tier always remains available.`,
  },
  {
    id: "intellectual-property",
    title: "6. Intellectual Property",
    body: `The JungleCoach application, website, logos, and all original content are owned by JungleCoach and protected by copyright law. You may not copy, distribute, modify, or create derivative works from our software or content without explicit written permission. All League of Legends game assets, champion names, and related intellectual property remain the property of Riot Games, Inc.`,
  },
  {
    id: "prohibited",
    title: "7. Prohibited Uses",
    body: `You agree not to:
• Use the Service to cheat, exploit, or gain an unfair in-game advantage beyond analytical coaching (e.g. scripting, botting, or memory reading)
• Attempt to reverse-engineer, decompile, or tamper with the JungleCoach application
• Share, resell, or transfer your account or subscription to another person
• Use the Service in a manner that violates Riot Games' Terms of Service or API policies
• Attempt to circumvent rate limits, access controls, or subscription tier restrictions
• Use the Service for any illegal purpose or in violation of applicable law`,
  },
  {
    id: "termination",
    title: "8. Termination",
    body: `We may suspend or terminate your access to the Service at any time, with or without notice, if you violate these Terms or if we discontinue the Service. Upon termination, your right to use the Service ceases immediately. You may cancel your account at any time from the Settings page. Cancellation takes effect at the end of the current billing period.`,
  },
  {
    id: "disclaimer",
    title: "9. Disclaimer of Warranties",
    body: `The Service is provided "as is" and "as available" without warranties of any kind, express or implied. We do not guarantee that the Service will be uninterrupted, error-free, or that suggestions provided are accurate or optimal. Coaching suggestions are analytical in nature and are not a substitute for your own in-game judgement.`,
  },
  {
    id: "liability",
    title: "10. Limitation of Liability",
    body: `To the maximum extent permitted by applicable law, JungleCoach and its operators shall not be liable for any indirect, incidental, special, consequential, or punitive damages arising from your use of the Service. Our total liability to you for any claim arising from these Terms or the Service shall not exceed the amount you paid to us in the 12 months preceding the claim.`,
  },
  {
    id: "changes",
    title: "11. Changes to These Terms",
    body: `We may update these Terms from time to time. We will notify you of material changes by email or by posting a notice on the website. Continued use of the Service after changes take effect constitutes your acceptance of the new Terms. If you disagree with a change, you may cancel your account before the change takes effect.`,
  },
  {
    id: "contact",
    title: "12. Contact",
    body: `If you have questions about these Terms, please contact us at: support@junglecoach.gg`,
  },
];

export default function TermsPage() {
  return (
    <div className="min-h-screen" style={{ background: "#080818" }}>
      {/* Nav */}
      <header
        className="sticky top-0 z-50 border-b px-6 py-4 backdrop-blur-md"
        style={{ borderColor: "rgba(26,26,74,0.8)", background: "rgba(8,8,24,0.85)" }}
      >
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <Link href="/" className="arcane-heading text-lg font-bold" style={{ color: "#f0c040" }}>
            JungleCoach
          </Link>
          <Link
            href="/"
            className="sub-heading text-xs tracking-widest transition-colors"
            style={{ color: "#7986cb" }}
          >
            ← Back
          </Link>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-4xl mx-auto px-6 py-16">
        {/* Header */}
        <div className="mb-12">
          <p className="sub-heading text-xs tracking-widest mb-3" style={{ color: "#7986cb" }}>
            LEGAL
          </p>
          <h1 className="arcane-heading text-4xl md:text-5xl mb-4" style={{ color: "#f0c040" }}>
            Terms of Service
          </h1>
          <p className="text-sm" style={{ color: "#7986cb" }}>
            Last updated: 27 April 2026
          </p>
        </div>

        {/* Table of contents */}
        <nav
          className="arcane-card rounded-xl p-6 mb-12"
          style={{ borderColor: "rgba(26,26,74,0.8)" }}
        >
          <p className="sub-heading text-xs tracking-widest mb-4" style={{ color: "#7986cb" }}>
            CONTENTS
          </p>
          <ol className="space-y-1">
            {SECTIONS.map((s) => (
              <li key={s.id}>
                <a
                  href={`#${s.id}`}
                  className="text-sm transition-colors hover:underline"
                  style={{ color: "#c5cae9" }}
                >
                  {s.title}
                </a>
              </li>
            ))}
          </ol>
        </nav>

        {/* Sections */}
        <div className="space-y-10">
          {SECTIONS.map((s) => (
            <section key={s.id} id={s.id} className="scroll-mt-24">
              <h2
                className="arcane-heading text-xl mb-3"
                style={{ color: "#c5cae9" }}
              >
                {s.title}
              </h2>
              <div
                className="border-l-2 pl-5"
                style={{ borderColor: "rgba(240,192,64,0.3)" }}
              >
                {s.body.split("\n").map((line, i) =>
                  line.trim() === "" ? (
                    <div key={i} className="h-3" />
                  ) : (
                    <p key={i} className="text-sm leading-relaxed" style={{ color: "#c5cae9" }}>
                      {line}
                    </p>
                  )
                )}
              </div>
            </section>
          ))}
        </div>
      </main>

      {/* Footer */}
      <footer
        className="border-t px-6 py-8 mt-16"
        style={{ borderColor: "rgba(26,26,74,0.8)" }}
      >
        <div className="max-w-4xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <span className="arcane-heading text-base font-bold" style={{ color: "#f0c040" }}>
            JungleCoach
          </span>
          <p className="text-xs text-center" style={{ color: "#7986cb" }}>
            JungleCoach isn&apos;t endorsed by Riot Games and doesn&apos;t reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties.
          </p>
          <div className="flex gap-4">
            <Link href="/terms" className="sub-heading text-xs tracking-widest" style={{ color: "#f0c040" }}>
              Terms
            </Link>
            <Link href="/privacy" className="sub-heading text-xs tracking-widest transition-colors" style={{ color: "#7986cb" }}>
              Privacy
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
