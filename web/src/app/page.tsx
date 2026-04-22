"use client";

import Link from "next/link";
import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence, useScroll, useTransform } from "framer-motion";
import { OverlayDemo } from "@/components/landing/OverlayDemo";
import { createClient } from "@/lib/supabase";

// ─── Champion ambient color palette ──────────────────────────────────────────

interface JungleChamp {
  name: string;
  ddragon: string;
  h: number;
  s: string;
  l: string;
}

const JUNGLE_CHAMPS: JungleChamp[] = [
  { name: "Hecarim",  ddragon: "Hecarim",  h: 150, s: "55%", l: "14%" },
  { name: "Vi",       ddragon: "Vi",       h: 330, s: "55%", l: "15%" },
  { name: "Warwick",  ddragon: "Warwick",  h: 20,  s: "65%", l: "14%" },
  { name: "Ekko",     ddragon: "Ekko",     h: 180, s: "65%", l: "14%" },
  { name: "Lee Sin",  ddragon: "LeeSin",   h: 30,  s: "70%", l: "15%" },
  { name: "Kha'Zix",  ddragon: "Khazix",  h: 270, s: "55%", l: "13%" },
  { name: "Evelynn",  ddragon: "Evelynn",  h: 310, s: "60%", l: "15%" },
  { name: "Kayn",     ddragon: "Kayn",     h: 285, s: "50%", l: "13%" },
];

function getDragonUrl(ddragon: string) {
  return `https://ddragon.leagueoflegends.com/cdn/img/champion/splash/${ddragon}_0.jpg`;
}

// ─── Runic particle field ─────────────────────────────────────────────────────

const RUNES = ["ᚠ", "ᚢ", "ᚦ", "ᚨ", "ᚱ", "ᚲ", "ᚷ", "ᚹ", "ᚺ", "ᚾ", "ᛁ", "ᛃ", "ᛇ", "ᛈ", "ᛉ", "ᛊ", "ᛏ", "ᛒ", "ᛖ", "ᛗ", "ᛚ", "ᛜ", "ᛞ", "ᛟ"];

interface Particle {
  id: number;
  x: number;
  y: number;
  rune: string;
  size: number;
  duration: number;
  delay: number;
  opacity: number;
  drift: number;
}

function RunicParticles() {
  const [particles, setParticles] = useState<Particle[]>([]);

  useEffect(() => {
    const ps: Particle[] = Array.from({ length: 28 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      rune: RUNES[Math.floor(Math.random() * RUNES.length)],
      size: 10 + Math.random() * 14,
      duration: 12 + Math.random() * 20,
      delay: Math.random() * 8,
      opacity: 0.04 + Math.random() * 0.1,
      drift: (Math.random() - 0.5) * 60,
    }));
    setParticles(ps);
  }, []);

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {particles.map((p) => (
        <motion.span
          key={p.id}
          className="absolute select-none text-[#00e5ff]"
          style={{
            left: `${p.x}%`,
            top: `${p.y}%`,
            fontSize: p.size,
            opacity: p.opacity,
            fontFamily: "serif",
          }}
          animate={{
            y: [0, -80, 0],
            x: [0, p.drift, 0],
            opacity: [p.opacity, p.opacity * 2.5, p.opacity],
            rotate: [0, 15, -10, 0],
          }}
          transition={{
            duration: p.duration,
            delay: p.delay,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        >
          {p.rune}
        </motion.span>
      ))}
    </div>
  );
}

// ─── Aurora gradient background ──────────────────────────────────────────────

function AuroraBackground({ ambientH, ambientS, ambientL }: { ambientH: number; ambientS: string; ambientL: string }) {
  return (
    <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
      <motion.div
        className="absolute inset-0"
        animate={{
          background: [
            `radial-gradient(ellipse 80% 60% at 20% 20%, hsl(${ambientH},${ambientS},${ambientL}) 0%, transparent 60%), radial-gradient(ellipse 60% 80% at 80% 80%, hsl(${(ambientH + 60) % 360},60%,12%) 0%, transparent 60%), radial-gradient(ellipse 100% 80% at 50% 50%, #080818 40%, transparent 100%)`,
          ],
        }}
        transition={{ duration: 2, ease: "easeInOut" }}
        style={{
          background: `radial-gradient(ellipse 80% 60% at 20% 20%, hsl(${ambientH},${ambientS},${ambientL}) 0%, transparent 60%), radial-gradient(ellipse 60% 80% at 80% 80%, hsl(${(ambientH + 60) % 360},60%,12%) 0%, transparent 60%), radial-gradient(ellipse 100% 80% at 50% 50%, #080818 40%, transparent 100%)`,
        }}
      />
      {/* Slow hue-rotating mesh */}
      <motion.div
        className="absolute inset-0 opacity-30"
        animate={{ filter: ["hue-rotate(0deg)", "hue-rotate(40deg)", "hue-rotate(0deg)"] }}
        transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
        style={{
          background: "linear-gradient(135deg, rgba(0,229,255,0.08) 0%, rgba(200,80,255,0.06) 50%, rgba(240,192,64,0.08) 100%)",
        }}
      />
    </div>
  );
}

// ─── Data ────────────────────────────────────────────────────────────────────

const STEPS = [
  { n: "01", title: "Riot Live Client API", body: "JungleCoach connects to Riot's official Live Client API — a local service Riot provides during every active game. No screen capture, no image processing." },
  { n: "02", title: "Champion detection", body: "All 10 champions, their roles, CS, kill scores, and game time are read directly from the game client in real time. Always accurate, always instant." },
  { n: "03", title: "Matchup data", body: "Win-rates, power spikes, and counter data are pulled from a local cache sourced from U.GG and LoLalytics." },
  { n: "04", title: "AI analysis", body: "Claude analyses matchup dynamics, game phase, CS differentials, and kill pressure across all three lanes simultaneously." },
  { n: "05", title: "Live overlay", body: "A ranked gank priority appears above your game — colour coded, with a one-sentence reason for each lane." },
];

const FEATURES = [
  { title: "Real-time, not post-game", body: "Refreshes every 5 seconds. Priority shifts the moment the game state changes — not in a stat summary after you've already lost." },
  { title: "All 3 lanes, ranked", body: "AI weighs matchup win-rates, game phase, and gank difficulty to rank Top, Mid, and Bot every refresh." },
  { title: "Natural language reasoning", body: "\"Riven hard counters GP early. One gank ends the lane.\" Not just a colour — a reason you can act on." },
  { title: "Game phase awareness", body: "A Kassadin at minute 8 is not worth ganking for. The model knows which champions scale and adjusts priority accordingly." },
  { title: "Lightweight overlay", body: "A slim, semi-transparent panel sits above the game. Draggable, toggleable with a hotkey, never blocks your view." },
  { title: "Privacy first", body: "No sensitive game data leaves your machine. The AI sees only champion names and basic game state — sent to our servers solely to generate your suggestions." },
];

const PLANS = [
  {
    key: "free", name: "Free", price: "€0", period: "forever", badge: null,
    features: [
      "Live overlay — unlimited games",
      "Suggestions refresh every 10s (no reasoning)",
      "2 post-game analyses / month",
    ],
    cta: "Get started", href: "/signup", highlight: false, accent: "cyan",
  },
  {
    key: "premium_monthly", name: "Premium", price: "€7.99", period: "/ month", badge: "MOST POPULAR",
    features: [
      "Live overlay at full speed (5s refresh)",
      "Full reasoning with every suggestion",
      "15 post-game analyses / week",
      "Full history dashboard",
      "No ads",
    ],
    cta: "Start Premium", href: "/signup?plan=premium_monthly", highlight: true, accent: "gold",
  },
  {
    key: "premium_annual", name: "Premium Annual", price: "€59.99", period: "/ year", badge: "SAVE €36",
    features: [
      "Everything in Premium",
      "Billed annually — save €36 vs monthly",
    ],
    cta: "Get annual", href: "/signup?plan=premium_annual", highlight: false, accent: "cyan",
  },
  {
    key: "pro_monthly", name: "Pro", price: "€18.99", period: "/ month", badge: null,
    features: [
      "Everything in Premium",
      "35 post-game analyses / week",
      "Priority API queue (faster during peak hours)",
      "No ads",
    ],
    cta: "Go Pro", href: "/signup?plan=pro_monthly", highlight: false, accent: "magenta",
  },
];

const FAQS = [
  { q: "Is this against Riot's Terms of Service?", a: "No. JungleCoach uses Riot's official Live Client API — a local service Riot themselves provide during every active game. It reads only data the player can see, does not hook into the game process, and does not read memory. We are registered on the Riot Developer Portal." },
  { q: "Does it work while the game is running?", a: "Yes. The app connects to Riot's Live Client API in the background while League is running. Champion and game data updates automatically — no manual input or screen interaction needed." },
  { q: "What rank is this built for?", a: "Primarily Silver through Platinum — the ELO where the strategic gap between mid and high ranks is largest. High-ELO players who want a second opinion also find it useful." },
  { q: "What operating system does it support?", a: "Windows at launch. Mac and Linux support is planned for a future release." },
  { q: "Is there always a free tier?", a: "Yes, permanently. The free tier gives you the full live overlay experience. Riot requires every third-party tool to maintain a free option." },
  { q: "Does my game data get sent to a server?", a: "The only data that leaves your machine is champion names and basic game state (game time, CS, kill scores) — sent to our AI model to generate suggestions. No account details, replay data, or personal stats are ever uploaded." },
];

// ─── Animation helpers ────────────────────────────────────────────────────────

const fadeUp = {
  hidden: { opacity: 0, y: 28 },
  visible: (i = 0) => ({
    opacity: 1, y: 0,
    transition: { duration: 0.6, delay: i * 0.08, ease: [0.25, 0.46, 0.45, 0.94] as [number, number, number, number] },
  }),
};

function FadeIn({ children, delay = 0, className = "" }: { children: React.ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true, margin: "-40px" }} custom={delay} className={className}>
      {children}
    </motion.div>
  );
}

// ─── Nav ─────────────────────────────────────────────────────────────────────

function Nav() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getSession().then(({ data: { session } }) => setLoggedIn(!!session));
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_e, session) => setLoggedIn(!!session));
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => { subscription.unsubscribe(); window.removeEventListener("scroll", onScroll); };
  }, []);

  return (
    <nav className={`sticky top-0 z-50 px-6 py-4 transition-all duration-300 ${scrolled ? "border-b border-[#1a1a4a] bg-[#080818]/90 backdrop-blur-2xl" : "bg-transparent"}`}>
      <div className="max-w-7xl mx-auto grid grid-cols-3 items-center">
        <span className="arcane-heading text-lg font-bold tracking-wider justify-self-start" style={{ color: "#f0c040", textShadow: "0 0 20px rgba(240,192,64,0.5)" }}>
          JungleCoach
        </span>
        <div className="hidden md:flex items-center justify-center gap-8">
          {[["#how-it-works", "How it works"], ["#features", "Features"], ["#pricing", "Pricing"], ["#faq", "FAQ"]].map(([href, label]) => (
            <a key={href} href={href} className="sub-heading text-xs text-[#c5cae9] hover:text-white transition-colors tracking-widest">
              {label}
            </a>
          ))}
        </div>
        <div className="flex items-center justify-end gap-3">
          {loggedIn ? (
            <Link href="/dashboard" className="btn-arcane text-xs">Dashboard →</Link>
          ) : (
            <>
              <Link href="/login" className="sub-heading text-xs text-[#c5cae9] hover:text-white transition-colors tracking-widest">Log in</Link>
              <Link href="/signup" className="btn-arcane text-xs">Get started</Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}

// ─── Hero ─────────────────────────────────────────────────────────────────────

function HeroSection({ onAmbientChange }: { onAmbientChange: (h: number, s: string, l: string) => void }) {
  const heroRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const splashY = useTransform(scrollYProgress, [0, 1], ["0%", "20%"]);
  const splashOpacity = useTransform(scrollYProgress, [0, 0.8], [1, 0]);

  useEffect(() => {
    onAmbientChange(260, "60%", "12%");
  }, [onAmbientChange]);

  return (
    <section ref={heroRef} className="relative min-h-screen flex items-center overflow-hidden">
      {/* Full-bleed splash — Jinx */}
      <motion.div
        className="absolute inset-0 ken-burns"
        style={{ y: splashY, opacity: splashOpacity }}
      >
        <div
          className="absolute inset-0 bg-cover"
          style={{
            backgroundImage: `url(${getDragonUrl("Hecarim")})`,
            backgroundPosition: "center 15%",
            mixBlendMode: "luminosity",
            filter: "saturate(1.6) brightness(0.6)",
          }}
        />
      </motion.div>

      {/* Overlay gradients */}
      <div className="absolute inset-0 bg-gradient-to-r from-[#080818] via-[#080818]/80 to-transparent z-[1]" />
      <div className="absolute inset-0 bg-gradient-to-t from-[#080818] via-transparent to-transparent z-[1]" />

      <RunicParticles />

      <div className="relative z-[2] max-w-7xl mx-auto px-6 w-full grid lg:grid-cols-[60%_40%] gap-12 items-center py-32">
        <div>
          <motion.div
            variants={fadeUp} initial="hidden" animate="visible" custom={0}
            className="inline-flex items-center gap-2 mb-8"
          >
            <span className="sub-heading text-[10px] text-[#00e5ff] tracking-[0.25em] bg-[#00e5ff]/10 border border-[#00e5ff]/20 px-3 py-1.5 rounded-full">
              COMING SOON — NOT YET RELEASED
            </span>
          </motion.div>

          <motion.h1
            variants={fadeUp} initial="hidden" animate="visible" custom={1}
            className="arcane-heading text-5xl md:text-6xl lg:text-7xl font-black leading-[1.0] mb-6"
          >
            <span className="text-[#f0f2ff]">Know exactly</span>
            <br />
            <span style={{ color: "#f0c040" }}>where to gank</span>
            <br />
            <span className="text-[#f0f2ff] text-4xl md:text-5xl lg:text-6xl">before you look.</span>
          </motion.h1>

          <motion.p
            variants={fadeUp} initial="hidden" animate="visible" custom={2}
            className="text-lg text-[#c5cae9] leading-relaxed mb-10 max-w-xl font-light"
          >
            JungleCoach connects to Riot&apos;s Live Client API and delivers AI-powered
            gank priority for every lane — live, while you play.
          </motion.p>

          <motion.div
            variants={fadeUp} initial="hidden" animate="visible" custom={3}
            className="flex flex-col sm:flex-row gap-4"
          >
            <Link href="/signup" className="btn-arcane">Start for free</Link>
            <a href="#how-it-works" className="btn-arcane-ghost">How it works</a>
          </motion.div>

          {/* Stat strip */}
          <motion.div
            variants={fadeUp} initial="hidden" animate="visible" custom={4}
            className="mt-12 flex gap-8"
          >
            {[["5s", "refresh rate"], ["10", "champions tracked"], ["3", "lanes ranked"]].map(([val, lbl]) => (
              <div key={lbl}>
                <div className="arcane-heading text-2xl font-bold" style={{ color: "#f0c040" }}>{val}</div>
                <div className="sub-heading text-[10px] text-[#c5cae9] tracking-widest mt-0.5">{lbl}</div>
              </div>
            ))}
          </motion.div>
        </div>

        <motion.div
          variants={fadeUp} initial="hidden" animate="visible" custom={5}
          className="flex justify-center lg:justify-end"
        >
          <OverlayDemo />
        </motion.div>
      </div>

      {/* Bottom diagonal */}
      <div className="absolute bottom-0 left-0 right-0 h-32 z-[2]" style={{ background: "linear-gradient(to bottom, transparent, #080818)" }} />
    </section>
  );
}

// ─── Champion card grid ───────────────────────────────────────────────────────

function ChampionSection({ onAmbientChange }: { onAmbientChange: (h: number, s: string, l: string) => void }) {
  const [activeChamp, setActiveChamp] = useState<string | null>(null);

  const handleEnter = useCallback((champ: JungleChamp) => {
    setActiveChamp(champ.name);
    onAmbientChange(champ.h, champ.s, champ.l);
  }, [onAmbientChange]);

  const handleLeave = useCallback(() => {
    setActiveChamp(null);
    onAmbientChange(260, "60%", "12%");
  }, [onAmbientChange]);

  return (
    <section className="relative px-6 py-24 z-10">
      <div className="max-w-7xl mx-auto">
        <FadeIn className="text-center mb-12">
          <p className="sub-heading text-xs text-[#00e5ff] tracking-[0.25em] mb-3">JUNGLECOACH KNOWS EVERY MATCHUP</p>
          <h2 className="arcane-heading text-3xl md:text-4xl font-bold text-[#f0f2ff]">Every champion. Every matchup.</h2>
        </FadeIn>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {JUNGLE_CHAMPS.map((champ, i) => {
            const isActive = activeChamp === champ.name;
            return (
              <FadeIn key={champ.name} delay={i * 0.4}>
                <motion.div
                  className="relative rounded-xl overflow-hidden cursor-pointer group"
                  style={{ aspectRatio: "1215/717", border: "1px solid rgba(255,255,255,0.08)" }}
                  onHoverStart={() => handleEnter(champ)}
                  onHoverEnd={handleLeave}
                  whileHover={{ scale: 1.03, zIndex: 10 }}
                  transition={{ duration: 0.3 }}
                >
                  <div
                    className="absolute inset-0 transition-transform duration-700 group-hover:scale-105"
                    style={{
                      backgroundImage: `url(${getDragonUrl(champ.ddragon)})`,
                      backgroundSize: "100% 100%",
                      backgroundPosition: "center center",
                      mixBlendMode: "luminosity",
                      filter: "saturate(1.7) brightness(0.6)",
                    }}
                  />

                  <div
                    className="absolute inset-0 transition-opacity duration-300"
                    style={{
                      background: `hsl(${champ.h}, ${champ.s}, 30%)`,
                      mixBlendMode: "color-dodge",
                      opacity: isActive ? 0.5 : 0.18,
                    }}
                  />

                  <motion.div
                    className="absolute inset-0 pointer-events-none"
                    animate={{ opacity: isActive ? 1 : 0 }}
                    transition={{ duration: 0.4 }}
                    style={{
                      background: `radial-gradient(circle at 50% 100%, hsl(${champ.h},${champ.s},45%) 0%, transparent 65%)`,
                      mixBlendMode: "screen",
                    }}
                  />

                  <motion.div
                    className="absolute inset-0 rounded-xl pointer-events-none"
                    animate={{
                      boxShadow: isActive
                        ? `inset 0 0 0 1px hsl(${champ.h},${champ.s},50%), 0 0 40px hsl(${champ.h},${champ.s},28%)`
                        : "inset 0 0 0 1px rgba(255,255,255,0.08)",
                    }}
                    transition={{ duration: 0.3 }}
                  />

                  <div className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-black/80 to-transparent">
                    <span className="sub-heading text-xs font-bold tracking-widest text-white">{champ.name.toUpperCase()}</span>
                  </div>
                </motion.div>
              </FadeIn>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// ─── How It Works ─────────────────────────────────────────────────────────────

function HowItWorksSection() {
  return (
    <section id="how-it-works" className="relative px-6 py-24 z-10">
      {/* diagonal top */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[#1a1a4a] to-transparent" />

      <div className="max-w-5xl mx-auto">
        <FadeIn className="text-center mb-16">
          <p className="sub-heading text-xs text-[#f0c040] tracking-[0.25em] mb-3">HOW IT WORKS</p>
          <h2 className="arcane-heading text-3xl md:text-4xl font-bold text-[#f0f2ff]">From game start to suggestion in seconds</h2>
        </FadeIn>

        <div className="relative">
          <div className="absolute left-[19px] top-3 bottom-3 w-px bg-gradient-to-b from-[#f0c040]/40 via-[#c850ff]/20 to-transparent hidden md:block" />
          <div className="space-y-8">
            {STEPS.map((step, i) => (
              <FadeIn key={step.n} delay={i}>
                <motion.div
                  className="flex gap-6 group"
                  whileHover={{ x: 4 }}
                  transition={{ duration: 0.2 }}
                >
                  <div
                    className="shrink-0 w-10 h-10 rounded-full flex items-center justify-center z-10 border"
                    style={{
                      background: "rgba(13,13,43,0.9)",
                      borderColor: "rgba(240,192,64,0.3)",
                      boxShadow: "0 0 16px rgba(240,192,64,0.1)",
                    }}
                  >
                    <span className="sub-heading text-[10px] font-bold" style={{ color: "#f0c040" }}>{step.n}</span>
                  </div>
                  <div className="pt-2 pb-2">
                    <h3 className="sub-heading text-base font-bold text-[#f0f2ff] mb-1.5 tracking-wide group-hover:text-[#f0c040] transition-colors">{step.title}</h3>
                    <p className="text-sm text-[#c5cae9] leading-relaxed max-w-xl">{step.body}</p>
                  </div>
                </motion.div>
              </FadeIn>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Features ─────────────────────────────────────────────────────────────────

function FeaturesSection() {
  return (
    <section id="features" className="relative px-6 py-24 z-10">
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[#1a1a4a] to-transparent" />

      {/* Diagonal background panel */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: "linear-gradient(135deg, rgba(0,229,255,0.03) 0%, rgba(200,80,255,0.03) 100%)",
          clipPath: "polygon(0 5%, 100% 0, 100% 95%, 0 100%)",
        }}
      />

      <div className="max-w-7xl mx-auto">
        <FadeIn className="text-center mb-16">
          <p className="sub-heading text-xs text-[#c850ff] tracking-[0.25em] mb-3">FEATURES</p>
          <h2 className="arcane-heading text-3xl md:text-4xl font-bold text-[#f0f2ff]">Built for junglers who want an edge</h2>
        </FadeIn>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURES.map((f, i) => (
            <FadeIn key={f.title} delay={i}>
              <motion.div
                className="arcane-card p-6 h-full cursor-default relative overflow-hidden"
                whileHover={{ scale: 1.02 }}
              >
                {/* Radial sweep on hover */}
                <motion.div
                  className="absolute inset-0 pointer-events-none opacity-0"
                  whileHover={{ opacity: 1 }}
                  style={{ background: "radial-gradient(circle at 50% 0%, rgba(240,192,64,0.06) 0%, transparent 70%)" }}
                />
                <h3 className="sub-heading text-sm font-bold text-[#f0f2ff] mb-2 tracking-wide">{f.title}</h3>
                <p className="text-sm text-[#c5cae9] leading-relaxed">{f.body}</p>
              </motion.div>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Pricing ──────────────────────────────────────────────────────────────────

const ACCENT_STYLES = {
  gold:    { border: "rgba(240,192,64,0.35)",  glow: "rgba(240,192,64,0.1)",  text: "#f0c040",  bg: "rgba(240,192,64,0.08)"  },
  cyan:    { border: "rgba(0,229,255,0.25)",   glow: "rgba(0,229,255,0.07)",  text: "#00e5ff",  bg: "rgba(0,229,255,0.05)"   },
  magenta: { border: "rgba(200,80,255,0.25)",  glow: "rgba(200,80,255,0.07)", text: "#c850ff",  bg: "rgba(200,80,255,0.05)"  },
};

function PricingSection() {
  return (
    <section id="pricing" className="relative px-6 py-24 z-10">
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[#1a1a4a] to-transparent" />

      <div className="max-w-7xl mx-auto">
        <FadeIn className="text-center mb-16">
          <p className="sub-heading text-xs text-[#f0c040] tracking-[0.25em] mb-3">PRICING</p>
          <h2 className="arcane-heading text-3xl md:text-4xl font-bold text-[#f0f2ff]">Subscription Plans</h2>
        </FadeIn>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          {PLANS.map((plan, i) => {
            const accent = ACCENT_STYLES[plan.accent as keyof typeof ACCENT_STYLES];
            return (
              <FadeIn key={plan.key} delay={i}>
                <motion.div
                  className="relative rounded-xl border h-full flex flex-col"
                  style={{
                    padding: plan.badge ? "2.5rem 1.5rem 1.5rem" : "1.5rem",
                    background: "rgba(20,20,60,0.75)",
                    borderColor: plan.highlight ? accent.border : "rgba(80,90,180,0.35)",
                    boxShadow: plan.highlight ? `0 0 50px ${accent.glow}` : "none",
                    backdropFilter: "blur(16px)",
                  }}
                  whileHover={{
                    borderColor: accent.border,
                    boxShadow: `0 0 50px ${accent.glow}, inset 0 0 40px ${accent.bg}`,
                    y: -4,
                  }}
                  transition={{ duration: 0.3 }}
                >
                  {plan.badge && (
                    <div
                      className="absolute -top-3 left-1/2 -translate-x-1/2 sub-heading text-[10px] font-bold px-3 py-1 rounded-full tracking-[0.15em] whitespace-nowrap"
                      style={{ background: plan.highlight ? accent.text : "#1a1a4a", color: plan.highlight ? "#080818" : "#c5cae9" }}
                    >
                      {plan.badge}
                    </div>
                  )}

                  <div className="mb-5">
                    <p className="sub-heading text-[10px] font-bold tracking-[0.2em] mb-3" style={{ color: accent.text }}>{plan.name.toUpperCase()}</p>
                    <div className="flex items-baseline gap-1">
                      <span className="arcane-heading text-3xl font-bold text-[#f0f2ff]">{plan.price}</span>
                      <span className="text-xs text-[#c5cae9]">{plan.period}</span>
                    </div>
                  </div>

                  <ul className="space-y-2.5 mb-6 flex-1">
                    {plan.features.map((feat) => (
                      <li key={feat} className="flex items-start gap-2 text-sm text-[#c5cae9]">
                        <span className="mt-0.5 shrink-0 text-xs" style={{ color: accent.text }}>✦</span>
                        {feat}
                      </li>
                    ))}
                  </ul>

                  <Link
                    href={plan.href}
                    className="block w-full text-center py-2.5 rounded-lg font-bold text-sm sub-heading tracking-widest transition-all duration-200"
                    style={{
                      background: plan.highlight ? accent.text : "transparent",
                      color: plan.highlight ? "#080818" : accent.text,
                      border: plan.highlight ? "none" : `1px solid ${accent.border}`,
                    }}
                  >
                    {plan.cta}
                  </Link>
                </motion.div>
              </FadeIn>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// ─── FAQ ──────────────────────────────────────────────────────────────────────

function FAQSection() {
  const [open, setOpen] = useState<number | null>(null);

  return (
    <section id="faq" className="relative px-6 py-24 z-10">
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[#1a1a4a] to-transparent" />

      <div className="max-w-2xl mx-auto">
        <FadeIn className="text-center mb-16">
          <p className="sub-heading text-xs text-[#c850ff] tracking-[0.25em] mb-3">FAQ</p>
          <h2 className="arcane-heading text-3xl md:text-4xl font-bold text-[#f0f2ff]">Common questions</h2>
        </FadeIn>

        <div className="space-y-2">
          {FAQS.map((faq, i) => (
            <FadeIn key={i} delay={i * 0.5}>
              <motion.div
                className="rounded-xl overflow-hidden border"
                style={{
                  background: "rgba(13,13,43,0.7)",
                  borderColor: open === i ? "rgba(200,80,255,0.3)" : "rgba(26,26,74,0.8)",
                  backdropFilter: "blur(12px)",
                }}
                animate={{ borderColor: open === i ? "rgba(200,80,255,0.3)" : "rgba(26,26,74,0.8)" }}
              >
                <button
                  onClick={() => setOpen(open === i ? null : i)}
                  className="w-full flex items-center justify-between px-5 py-4 text-left"
                >
                  <span className="text-sm font-medium text-[#f0f2ff] pr-4">{faq.q}</span>
                  <motion.span
                    animate={{ rotate: open === i ? 45 : 0, color: open === i ? "#c850ff" : "#7986cb" }}
                    transition={{ duration: 0.2 }}
                    className="shrink-0 text-lg leading-none"
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
                      <p className="px-5 pb-4 text-sm text-[#c5cae9] leading-relaxed border-t border-[#1a1a4a] pt-3">
                        {faq.a}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Download CTA ─────────────────────────────────────────────────────────────

function DownloadSection() {
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getSession().then(({ data: { session } }) => setLoggedIn(!!session));
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_e, session) => setLoggedIn(!!session));
    return () => subscription.unsubscribe();
  }, []);

  return (
    <section id="download" className="relative px-6 py-24 z-10">
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[#1a1a4a] to-transparent" />

      <div className="max-w-3xl mx-auto text-center">
        <FadeIn>
          <motion.div
            className="relative rounded-2xl p-16 overflow-hidden border noise-overlay"
            style={{
              background: "rgba(20,20,60,0.75)",
              borderColor: "rgba(240,192,64,0.2)",
              backdropFilter: "blur(20px)",
              boxShadow: "0 0 80px rgba(240,192,64,0.08), 0 0 160px rgba(200,80,255,0.05)",
            }}
            whileHover={{
              borderColor: "rgba(240,192,64,0.45)",
              boxShadow: "0 0 100px rgba(240,192,64,0.14), 0 0 160px rgba(200,80,255,0.07)",
              y: -4,
            }}
            transition={{ duration: 0.3 }}
          >
            {/* Ambient glows */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[500px] h-[250px] rounded-full pointer-events-none" style={{ background: "radial-gradient(ellipse, rgba(240,192,64,0.08) 0%, transparent 70%)" }} />
            <div className="absolute bottom-0 right-0 w-[300px] h-[200px] rounded-full pointer-events-none" style={{ background: "radial-gradient(ellipse, rgba(200,80,255,0.06) 0%, transparent 70%)" }} />

            {/* Splash peeking behind — Ekko */}
            <div
              className="absolute inset-0 opacity-10"
              style={{
                backgroundImage: `url(${getDragonUrl("Ekko")})`,
                backgroundSize: "cover",
                backgroundPosition: "center top",
                mixBlendMode: "luminosity",
              }}
            />

            <div className="relative z-10">
              <p className="sub-heading text-xs text-[#f0c040] tracking-[0.25em] mb-4">READY TO CLIMB</p>
              <h2 className="arcane-heading text-4xl font-black mb-4" style={{ color: "#f0c040" }}>
                Dominate the jungle.
              </h2>
              <p className="text-[#c5cae9] text-sm mb-10 leading-relaxed max-w-lg mx-auto">
                Free to download. Free to try. No credit card required.<br />
                Windows only — Mac support coming soon.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                {loggedIn ? (
                  <Link href="/dashboard" className="btn-arcane">Go to dashboard</Link>
                ) : (
                  <Link href="/signup" className="btn-arcane">Create account &amp; download</Link>
                )}
                <a href="#pricing" className="btn-arcane-ghost">View pricing</a>
              </div>
            </div>
          </motion.div>
        </FadeIn>
      </div>
    </section>
  );
}

// ─── Footer ───────────────────────────────────────────────────────────────────

function Footer() {
  return (
    <footer className="relative border-t px-6 py-8 z-10" style={{ borderColor: "rgba(26,26,74,0.8)" }}>
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <span className="arcane-heading text-base font-bold" style={{ color: "#f0c040" }}>JungleCoach</span>
        <p className="text-xs text-center" style={{ color: "#7986cb" }}>
          JungleCoach is not affiliated with Riot Games. League of Legends is a trademark of Riot Games, Inc.
        </p>
        <div className="flex gap-4">
          <Link href="/login" className="sub-heading text-xs tracking-widest transition-colors" style={{ color: "#7986cb" }}>Log in</Link>
          <Link href="/signup" className="sub-heading text-xs tracking-widest transition-colors" style={{ color: "#7986cb" }}>Sign up</Link>
        </div>
      </div>
    </footer>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  const [ambientH, setAmbientH] = useState(260);
  const [ambientS, setAmbientS] = useState("60%");
  const [ambientL, setAmbientL] = useState("12%");

  const handleAmbient = useCallback((h: number, s: string, l: string) => {
    setAmbientH(h);
    setAmbientS(s);
    setAmbientL(l);
  }, []);

  return (
    <div className="flex flex-col min-h-screen relative">
      <AuroraBackground ambientH={ambientH} ambientS={ambientS} ambientL={ambientL} />
      <Nav />
      <HeroSection onAmbientChange={handleAmbient} />
      <ChampionSection onAmbientChange={handleAmbient} />
      <HowItWorksSection />
      <FeaturesSection />
      <PricingSection />
      <FAQSection />
      <DownloadSection />
      <Footer />
    </div>
  );
}
