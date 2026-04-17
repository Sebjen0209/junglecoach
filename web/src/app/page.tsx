"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { OverlayDemo } from "@/components/landing/OverlayDemo";
import { createClient } from "@/lib/supabase";

// ─── Data ─────────────────────────────────────────────────────────────────────

const STEPS = [
  {
    n: "01",
    title: "Screen capture",
    body: "The app captures your screen every ~3 seconds while League is running. Nothing is uploaded — all processing stays on your machine.",
  },
  {
    n: "02",
    title: "OCR scoreboard",
    body: "When you open the TAB scoreboard, OCR reads all 10 champion names and their roles in under a second.",
  },
  {
    n: "03",
    title: "Matchup data",
    body: "Win-rates, power spikes, and counter data are pulled from a local cache sourced from U.GG and LoLalytics.",
  },
  {
    n: "04",
    title: "AI analysis",
    body: "Claude analyses matchup dynamics, game phase, CS differentials, and kill pressure across all three lanes simultaneously.",
  },
  {
    n: "05",
    title: "Live overlay",
    body: "A ranked gank priority appears above your game — colour coded, with a one-sentence reason for each lane.",
  },
];

const FEATURES = [
  {
    title: "Real-time, not post-game",
    body: "Refreshes every 5 seconds. Priority shifts the moment the scoreboard changes — not in a stat summary after you've already lost.",
  },
  {
    title: "All 3 lanes, ranked",
    body: "AI weighs matchup win-rates, game phase, and gank difficulty to rank Top, Mid, and Bot every refresh.",
  },
  {
    title: "Natural language reasoning",
    body: "\"Riven hard counters GP early. One gank ends the lane.\" Not just a colour — a reason you can act on.",
  },
  {
    title: "Game phase awareness",
    body: "A Kassadin at minute 8 is not worth ganking for. The model knows which champions scale and adjusts priority accordingly.",
  },
  {
    title: "Lightweight overlay",
    body: "A slim, semi-transparent panel sits above the game. Draggable, toggleable with a hotkey, never blocks your view.",
  },
  {
    title: "Fully local",
    body: "No game data leaves your machine. The AI runs on our servers only when you open the scoreboard — and only sees champion names.",
  },
];

const PLANS = [
  {
    key: "free",
    name: "Free",
    price: "€0",
    period: "forever",
    badge: null,
    features: [
      "Live overlay — unlimited games",
      "Gank suggestions every 10s",
      "General priority (no match history)",
      "2 post-game analyses / month",
    ],
    cta: "Get started",
    href: "/signup",
    highlight: false,
  },
  {
    key: "premium_monthly",
    name: "Premium",
    price: "€7.99",
    period: "/ month",
    badge: "MOST POPULAR",
    features: [
      "Live overlay at full speed (5s refresh)",
      "10 post-game analyses / month",
      "Full history dashboard (90 days)",
      "Detailed coaching timeline per match",
    ],
    cta: "Start Premium",
    href: "/signup?plan=premium_monthly",
    highlight: true,
  },
  {
    key: "premium_annual",
    name: "Premium Annual",
    price: "€59.99",
    period: "/ year",
    badge: "2 MONTHS FREE",
    features: [
      "Everything in Premium",
      "Billed yearly — save €36",
    ],
    cta: "Get annual",
    href: "/signup?plan=premium_annual",
    highlight: false,
  },
  {
    key: "pro_monthly",
    name: "Pro",
    price: "€18.99",
    period: "/ month",
    badge: null,
    features: [
      "Everything in Premium",
      "20 post-game analyses / month",
      "Multi-account support (smurfs)",
      "Trend analysis — ward scores, gank rate",
      "Priority API queue",
    ],
    cta: "Go Pro",
    href: "/signup?plan=pro_monthly",
    highlight: false,
  },
];

const FAQS = [
  {
    q: "Is this against Riot's Terms of Service?",
    a: "No. JungleCoach reads only the TAB scoreboard — information you choose to open yourself. It does not hook into the game process, read memory, or access any data the player couldn't see normally. We are registered on the Riot Developer Portal.",
  },
  {
    q: "Does it work while the game is running?",
    a: "Yes. The app runs in the background and captures your screen passively. Open the TAB scoreboard any time and the overlay updates within seconds.",
  },
  {
    q: "What rank is this built for?",
    a: "Primarily Silver through Platinum — the ELO where the strategic gap between mid and high ranks is largest. High-ELO players who want a second opinion also find it useful.",
  },
  {
    q: "What operating system does it support?",
    a: "Windows at launch. Mac and Linux support is planned for a future release.",
  },
  {
    q: "Is there always a free tier?",
    a: "Yes, permanently. The free tier gives you the full live overlay experience. Riot requires every third-party tool to maintain a free option.",
  },
  {
    q: "Does my game data get sent to a server?",
    a: "The only data that leaves your machine is the list of champion names detected by OCR — sent to our AI model to generate suggestions. No game stats, account details, or replay data is ever uploaded.",
  },
];

// ─── Animation helpers ────────────────────────────────────────────────────────

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (i = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, delay: i * 0.07, ease: [0.25, 0.46, 0.45, 0.94] as [number, number, number, number] },
  }),
};

function FadeIn({ children, delay = 0, className = "" }: { children: React.ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      variants={fadeUp}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-50px" }}
      custom={delay}
      className={className}
    >
      {children}
    </motion.div>
  );
}

// ─── Sections ─────────────────────────────────────────────────────────────────

function Nav() {
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getSession().then(({ data: { session } }) => {
      setLoggedIn(!!session);
    });
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_e, session) => {
      setLoggedIn(!!session);
    });
    return () => subscription.unsubscribe();
  }, []);

  return (
    <nav className="sticky top-0 z-50 border-b border-[#1C1C2A] bg-[#07070D]/85 backdrop-blur-xl px-6 py-4">
      <div className="max-w-6xl mx-auto flex items-center justify-between">
        <span className="text-base font-bold text-white tracking-tight">
          JungleCoach<span className="text-[#E24B4A]">.</span>
        </span>
        <div className="hidden md:flex items-center gap-6">
          {[["#how-it-works", "How it works"], ["#features", "Features"], ["#pricing", "Pricing"], ["#faq", "FAQ"]].map(([href, label]) => (
            <a key={href} href={href} className="text-sm text-[#8080A0] hover:text-white transition-colors">
              {label}
            </a>
          ))}
        </div>
        <div className="flex items-center gap-2">
          {loggedIn ? (
            <Link
              href="/dashboard"
              className="text-sm bg-[#E24B4A] hover:bg-[#d03d3c] text-white px-4 py-2 rounded-lg font-semibold transition-colors"
            >
              Dashboard →
            </Link>
          ) : (
            <>
              <Link href="/login" className="text-sm text-[#8080A0] hover:text-white px-3 py-2 rounded-lg transition-colors">
                Log in
              </Link>
              <Link
                href="/signup"
                className="text-sm bg-[#E24B4A] hover:bg-[#d03d3c] text-white px-4 py-2 rounded-lg font-semibold transition-colors"
              >
                Get started
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}

function HeroSection() {
  return (
    <section className="relative overflow-hidden px-6 py-24 md:py-36">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-[#E24B4A]/5 blur-[140px] rounded-full" />
        <div className="absolute bottom-0 right-1/4 w-[400px] h-[300px] bg-[#E24B4A]/3 blur-[100px] rounded-full" />
      </div>

      <div className="max-w-6xl mx-auto grid lg:grid-cols-2 gap-16 items-center relative">
        <div>
          <motion.div
            variants={fadeUp} initial="hidden" animate="visible" custom={0}
            className="inline-flex items-center gap-2 bg-[#E24B4A]/10 border border-[#E24B4A]/20 text-[#E24B4A] text-[10px] font-bold px-3 py-1.5 rounded-full mb-8 tracking-[0.15em]"
          >
            NOW IN BETA
          </motion.div>

          <motion.h1
            variants={fadeUp} initial="hidden" animate="visible" custom={1}
            className="text-5xl md:text-6xl font-bold text-white leading-[1.06] tracking-tight mb-6"
          >
            Know exactly{" "}
            <span className="text-[#E24B4A]">where to gank</span>{" "}
            before you look at the map.
          </motion.h1>

          <motion.p
            variants={fadeUp} initial="hidden" animate="visible" custom={2}
            className="text-lg text-[#8080A0] leading-relaxed mb-10 max-w-lg"
          >
            JungleCoach reads your scoreboard via OCR and gives you AI-powered
            gank priority for every lane — live, while you play.
          </motion.p>

          <motion.div
            variants={fadeUp} initial="hidden" animate="visible" custom={3}
            className="flex flex-col sm:flex-row gap-3"
          >
            <Link href="/signup" className="btn-primary px-8 py-3.5 text-sm">
              Start for free
            </Link>
            <a href="#how-it-works" className="btn-ghost px-8 py-3.5 text-sm">
              How it works
            </a>
          </motion.div>
        </div>

        <motion.div
          variants={fadeUp} initial="hidden" animate="visible" custom={4}
          className="flex justify-center lg:justify-end"
        >
          <OverlayDemo />
        </motion.div>
      </div>
    </section>
  );
}

function HowItWorksSection() {
  return (
    <section id="how-it-works" className="px-6 py-24 border-t border-[#1C1C2A]">
      <div className="max-w-4xl mx-auto">
        <FadeIn className="text-center mb-16">
          <p className="text-[10px] font-bold text-[#E24B4A] tracking-[0.2em] mb-3">HOW IT WORKS</p>
          <h2 className="text-3xl md:text-4xl font-bold text-white">From scoreboard to suggestion in seconds</h2>
        </FadeIn>

        <div className="relative">
          <div className="absolute left-[19px] top-3 bottom-3 w-px bg-gradient-to-b from-[#E24B4A]/30 via-[#1C1C2A] to-transparent hidden md:block" />
          <div className="space-y-8">
            {STEPS.map((step, i) => (
              <FadeIn key={step.n} delay={i} className="flex gap-6">
                <div className="shrink-0 w-10 h-10 rounded-full bg-[#0E0E18] border border-[#1C1C2A] flex items-center justify-center z-10">
                  <span className="text-[10px] font-bold text-[#E24B4A]">{step.n}</span>
                </div>
                <div className="pt-2 pb-2">
                  <h3 className="text-white font-semibold mb-1.5">{step.title}</h3>
                  <p className="text-sm text-[#8080A0] leading-relaxed max-w-lg">{step.body}</p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function FeaturesSection() {
  return (
    <section id="features" className="px-6 py-24 border-t border-[#1C1C2A]">
      <div className="max-w-6xl mx-auto">
        <FadeIn className="text-center mb-16">
          <p className="text-[10px] font-bold text-[#E24B4A] tracking-[0.2em] mb-3">FEATURES</p>
          <h2 className="text-3xl md:text-4xl font-bold text-white">Built for junglers who want an edge</h2>
        </FadeIn>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
          {FEATURES.map((f, i) => (
            <FadeIn key={f.title} delay={i}>
              <motion.div
                whileHover={{ y: -3 }}
                transition={{ duration: 0.2 }}
                className="card card-hover p-6 h-full cursor-default"
              >
                <div className="w-1.5 h-1.5 rounded-full bg-[#E24B4A] mb-4" />
                <h3 className="text-white font-semibold mb-2 text-sm">{f.title}</h3>
                <p className="text-sm text-[#8080A0] leading-relaxed">{f.body}</p>
              </motion.div>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}

function PricingSection() {
  return (
    <section id="pricing" className="px-6 py-24 border-t border-[#1C1C2A]">
      <div className="max-w-6xl mx-auto">
        <FadeIn className="text-center mb-16">
          <p className="text-[10px] font-bold text-[#E24B4A] tracking-[0.2em] mb-3">PRICING</p>
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-3">Simple pricing</h2>
          <p className="text-[#8080A0] text-sm">Start free. Upgrade when you need more.</p>
        </FadeIn>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-3">
          {PLANS.map((plan, i) => (
            <FadeIn key={plan.key} delay={i}>
              <div
                className={`relative rounded-xl p-6 border h-full flex flex-col transition-all duration-200 ${
                  plan.highlight
                    ? "bg-[#0E0E18] border-[#E24B4A]/35 shadow-[0_0_40px_rgba(226,75,74,0.08)]"
                    : "bg-[#0E0E18] border-[#1C1C2A] hover:border-[#2A2A3A]"
                }`}
              >
                {plan.badge && (
                  <div className={`absolute -top-3 left-1/2 -translate-x-1/2 text-[10px] font-bold px-3 py-1 rounded-full tracking-[0.15em] whitespace-nowrap ${
                    plan.highlight ? "bg-[#E24B4A] text-white" : "bg-[#1C1C2A] text-[#8080A0]"
                  }`}>
                    {plan.badge}
                  </div>
                )}

                <div className="mb-5">
                  <p className="text-xs font-bold text-[#8080A0] uppercase tracking-widest mb-3">{plan.name}</p>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-bold text-white">{plan.price}</span>
                    <span className="text-xs text-[#46465C]">{plan.period}</span>
                  </div>
                </div>

                <ul className="space-y-2.5 mb-6 flex-1">
                  {plan.features.map((feat) => (
                    <li key={feat} className="flex items-start gap-2 text-sm text-[#8080A0]">
                      <span className="text-[#E24B4A] mt-0.5 shrink-0 text-xs">✓</span>
                      {feat}
                    </li>
                  ))}
                </ul>

                <Link
                  href={plan.href}
                  className={`block w-full text-center py-2.5 rounded-lg font-semibold text-sm transition-colors ${
                    plan.highlight
                      ? "bg-[#E24B4A] hover:bg-[#d03d3c] text-white"
                      : "border border-[#1C1C2A] hover:border-[#2A2A3A] text-[#8080A0] hover:text-white hover:bg-[#141422]"
                  }`}
                >
                  {plan.cta}
                </Link>
              </div>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}

function FAQSection() {
  const [open, setOpen] = useState<number | null>(null);

  return (
    <section id="faq" className="px-6 py-24 border-t border-[#1C1C2A]">
      <div className="max-w-2xl mx-auto">
        <FadeIn className="text-center mb-16">
          <p className="text-[10px] font-bold text-[#E24B4A] tracking-[0.2em] mb-3">FAQ</p>
          <h2 className="text-3xl md:text-4xl font-bold text-white">Common questions</h2>
        </FadeIn>

        <div className="space-y-2">
          {FAQS.map((faq, i) => (
            <FadeIn key={i} delay={i * 0.5}>
              <div className="border border-[#1C1C2A] rounded-xl overflow-hidden bg-[#0E0E18]">
                <button
                  onClick={() => setOpen(open === i ? null : i)}
                  className="w-full flex items-center justify-between px-5 py-4 text-left"
                >
                  <span className="text-sm font-medium text-white pr-4">{faq.q}</span>
                  <motion.span
                    animate={{ rotate: open === i ? 45 : 0 }}
                    transition={{ duration: 0.2 }}
                    className="text-[#46465C] shrink-0 text-lg leading-none"
                  >
                    +
                  </motion.span>
                </button>
                <AnimatePresence initial={false}>
                  {open === i && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.22, ease: "easeInOut" }}
                      className="overflow-hidden"
                    >
                      <p className="px-5 pb-4 text-sm text-[#8080A0] leading-relaxed border-t border-[#1C1C2A] pt-3">
                        {faq.a}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}

function DownloadSection() {
  return (
    <section id="download" className="px-6 py-24 border-t border-[#1C1C2A]">
      <div className="max-w-2xl mx-auto text-center">
        <FadeIn>
          <div className="relative bg-[#0E0E18] border border-[#1C1C2A] rounded-2xl p-12 overflow-hidden">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[400px] h-[200px] bg-[#E24B4A]/4 blur-[80px] rounded-full pointer-events-none" />
            <p className="text-[10px] font-bold text-[#E24B4A] tracking-[0.2em] mb-4 relative">DOWNLOAD</p>
            <h2 className="text-3xl font-bold text-white mb-4 relative">Ready to climb?</h2>
            <p className="text-[#8080A0] text-sm mb-8 leading-relaxed relative">
              Free to download. Free to try. No credit card required.
              Windows only — Mac support coming soon.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center relative">
              <Link href="/signup" className="btn-primary px-8 py-3.5 text-sm">
                Create account &amp; download
              </Link>
              <a href="#pricing" className="btn-ghost px-8 py-3.5 text-sm">
                View pricing
              </a>
            </div>
          </div>
        </FadeIn>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-[#1C1C2A] px-6 py-8">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <span className="text-sm font-bold text-white">
          JungleCoach<span className="text-[#E24B4A]">.</span>
        </span>
        <p className="text-xs text-[#46465C] text-center">
          JungleCoach is not affiliated with Riot Games. League of Legends is a trademark of Riot Games, Inc.
        </p>
        <div className="flex gap-4">
          <Link href="/login" className="text-xs text-[#46465C] hover:text-white transition-colors">Log in</Link>
          <Link href="/signup" className="text-xs text-[#46465C] hover:text-white transition-colors">Sign up</Link>
        </div>
      </div>
    </footer>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  return (
    <div className="flex flex-col min-h-screen">
      <Nav />
      <HeroSection />
      <HowItWorksSection />
      <FeaturesSection />
      <PricingSection />
      <FAQSection />
      <DownloadSection />
      <Footer />
    </div>
  );
}
