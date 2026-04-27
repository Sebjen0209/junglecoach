import Link from "next/link";

export const metadata = {
  title: "Privacy Policy — JungleCoach",
  description: "Privacy Policy for JungleCoach, a real-time League of Legends jungler assistant.",
};

const SECTIONS = [
  {
    id: "overview",
    title: "1. Overview",
    body: `JungleCoach ("we", "our", "us") is committed to protecting your privacy. This Privacy Policy explains what personal data we collect, how we use it, and your rights regarding that data. It applies to our website (junglecoach.gg), our desktop application, and all related services.

By using JungleCoach you agree to the collection and use of information as described in this policy.`,
  },
  {
    id: "data-collected",
    title: "2. Data We Collect",
    body: `Account data: When you create an account, we collect your email address and a hashed password (stored securely via Supabase Auth). We do not store plaintext passwords.

Subscription data: If you subscribe to a paid plan, Stripe processes your payment information. We store only your Stripe customer ID, subscription status, and current plan — not your card details.

Usage data: We collect anonymous analytics about feature usage (e.g. how often analyses are requested) to improve the product. This data is not linked to your identity.

Game data: The desktop application reads champion names and basic game state (CS, kills, game time) from Riot's local Live Client Data API during an active game. This data is sent to our cloud API solely to generate your coaching suggestions and is not stored beyond the duration of your session.

Post-game analysis: When you voluntarily submit a match ID for post-game coaching, we store the resulting analysis output linked to your account so you can review it later. Raw Riot timeline data is cached temporarily to avoid redundant API calls.`,
  },
  {
    id: "data-not-collected",
    title: "3. Data We Do Not Collect",
    body: `We do not collect:
• Your full name, address, or phone number
• IP addresses beyond what is automatically logged by our infrastructure
• Screen captures or recordings of your gameplay
• Any data from outside an active League of Legends game session
• Fog-of-war information or any game state not visible to the player
• Behavioural tracking cookies or advertising identifiers`,
  },
  {
    id: "how-we-use",
    title: "4. How We Use Your Data",
    body: `Account data is used to authenticate you, manage your subscription, and send transactional emails (e.g. password resets, billing confirmations). We do not send marketing emails unless you explicitly opt in.

Game data is used exclusively to generate your real-time coaching suggestions. It is processed by our cloud API (hosted on Railway) and by Anthropic's Claude API to produce natural language analysis. It is not stored, sold, or shared with any third party for any other purpose.

Post-game analysis data is stored so you can access your coaching history from the dashboard.

Aggregate, anonymised usage data may be used to improve the product and inform feature decisions.`,
  },
  {
    id: "third-parties",
    title: "5. Third-Party Services",
    body: `We use the following third-party services, each of which has its own privacy policy:

• Supabase — authentication and database hosting (supabase.com/privacy)
• Stripe — payment processing (stripe.com/privacy)
• Anthropic — AI analysis (anthropic.com/privacy); game state data is sent to Anthropic to generate suggestions
• Riot Games — we use the Riot Games Live Client Data API and Match API under Riot's API Terms of Service (developer.riotgames.com/terms)
• Railway — cloud API hosting; processes game data transiently
• Vercel — web app hosting
• Sentry — error tracking; may capture anonymised stack traces

We do not sell your data to any third party.`,
  },
  {
    id: "riot-data",
    title: "6. Riot Games Data",
    body: `JungleCoach accesses League of Legends game data via Riot Games' official APIs. This data belongs to Riot Games, Inc. and is used under licence. We use only:

• Live Client Data API — champion names, CS, kills, game time during an active game
• Match v5 API — match timeline data for post-game coaching (only when you submit a match ID)
• Summoner v4 API — to resolve Riot IDs submitted for post-game analysis

We do not store raw Riot API data indefinitely. Match timeline data is cached to avoid redundant API calls and may be retained for up to 90 days.

JungleCoach isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games and League of Legends are trademarks or registered trademarks of Riot Games, Inc.`,
  },
  {
    id: "data-retention",
    title: "7. Data Retention",
    body: `Account data is retained for as long as your account is active. If you delete your account, your email and account record are removed within 30 days.

Post-game analyses are retained for as long as your account is active and for up to 90 days after account deletion.

Match timeline cache data is retained for up to 90 days.

Stripe billing records are retained as required by financial regulations (typically 7 years).`,
  },
  {
    id: "security",
    title: "8. Security",
    body: `We take reasonable technical and organisational measures to protect your data:

• All data in transit is encrypted via HTTPS/TLS
• The local desktop backend binds only to 127.0.0.1 — it is not accessible from the network
• Authentication tokens are stored in Electron's secure OS keychain, not in localStorage
• Supabase Row Level Security ensures users can only access their own data
• API keys and secrets are stored only in server-side environment variables, never in the client or in the installer

No system is perfectly secure. In the event of a data breach, we will notify affected users as required by applicable law.`,
  },
  {
    id: "your-rights",
    title: "9. Your Rights",
    body: `Depending on your location, you may have the following rights under GDPR, CCPA, or other applicable law:

• Access: request a copy of the personal data we hold about you
• Correction: request correction of inaccurate data
• Deletion: request deletion of your account and associated data
• Portability: request your data in a machine-readable format
• Objection: object to certain uses of your data

To exercise any of these rights, contact us at privacy@junglecoach.gg. We will respond within 30 days.`,
  },
  {
    id: "cookies",
    title: "10. Cookies",
    body: `Our website uses only essential session cookies required for authentication (set by Supabase Auth). We do not use advertising cookies, third-party tracking cookies, or analytics cookies that identify individual users. You can disable cookies in your browser, but this will prevent you from logging in.`,
  },
  {
    id: "children",
    title: "11. Children's Privacy",
    body: `JungleCoach is not directed at children under the age of 13. We do not knowingly collect personal data from children under 13. If you believe a child under 13 has provided us with personal data, please contact us and we will delete it promptly.`,
  },
  {
    id: "changes",
    title: "12. Changes to This Policy",
    body: `We may update this Privacy Policy from time to time. We will notify you of material changes by email or by posting a notice on the website. The "last updated" date at the top of this page will reflect the most recent revision. Continued use of the Service after changes take effect constitutes your acceptance of the revised policy.`,
  },
  {
    id: "contact",
    title: "13. Contact",
    body: `For privacy-related questions or to exercise your data rights, contact us at:

privacy@junglecoach.gg

For general support: support@junglecoach.gg`,
  },
];

export default function PrivacyPage() {
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
            Privacy Policy
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
                style={{ borderColor: "rgba(0,229,255,0.3)" }}
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
            <Link href="/terms" className="sub-heading text-xs tracking-widest transition-colors" style={{ color: "#7986cb" }}>
              Terms
            </Link>
            <Link href="/privacy" className="sub-heading text-xs tracking-widest" style={{ color: "#f0c040" }}>
              Privacy
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
