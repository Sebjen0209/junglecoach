# JungleCoach — Product Vision

This file captures the full product idea, target user, market context, and monetisation
strategy. Read this alongside CLAUDE.md when working on anything product-facing:
landing page copy, feature design, pricing, onboarding, or marketing.

---

## The one-line pitch

A real-time AI assistant that watches your League of Legends game and tells the jungler
exactly where to gank, why, and what the long-term win condition is — updated live as
the game evolves.

---

## The problem we're solving

Playing jungle in League of Legends requires tracking an enormous amount of information
simultaneously: farming camps, watching the minimap, managing cooldowns, tracking the
enemy jungler, and constantly deciding which of three lanes is worth spending time in.

The strategic layer — "where should I be right now and why" — is one of the hardest
things to learn and the biggest differentiator between mid-ELO and high-ELO junglers.
Current tools (Mobalytics, Porofessor, Blitz) give you data. None of them give you
a live, role-specific decision. That gap is our product.

---

## Who we're building for

**Primary user: the jungle player in ranked, Silver through Platinum ELO**

They know the basics. They know what counters are. But in the heat of a game they
can't track all the matchup dynamics across three lanes while also playing their own
champion. They want to climb. They're willing to pay a small monthly fee for a tool
that genuinely helps them win more games.

**Secondary user: the climbing player who plays multiple roles**

They rotate between roles. When they play jungle, they want a smart co-pilot.

**Not our user (for now):** casual ARAM players, one-trick Challengers who already
know every matchup by heart, players who only play norms.

---

## How the tool works

1. The desktop app runs alongside the game, capturing the screen every ~3 seconds
2. When the player opens the TAB scoreboard, OCR reads all 10 champion names and roles
3. The app fetches matchup win-rate data from a local cache (sourced from U.GG / LoLalytics)
4. An AI model (Claude) analyses the matchup data, game phase, CS differentials, and
   kill pressure across all three lanes
5. A lightweight overlay displays a ranked gank priority — red (gank now), yellow
   (situational), grey (low priority) — with a 1-2 sentence reason per lane
6. This updates automatically as the game state changes

The analysis runs entirely on the user's machine. No game data is sent to our servers.

---

## What makes us different

- **Role-specific**: built exclusively for the jungler, not a generic stat tracker
- **Decisional, not informational**: we don't show you numbers, we tell you what to do
- **Natural language reasoning**: "Gank top — Riven hard counters GP and your laner
  is already winning CS. One successful gank ends the lane." Not just a red dot.
- **Game phase awareness**: we know that a champion weak early but dominant late
  changes the gank calculus completely. A Kassadin mid at minute 8 is not worth
  ganking for — but helping them survive to minute 20 is worth everything.
- **Lightweight and standalone**: no Overwolf dependency, no bloat, our brand only

---

## Competitive landscape

| Tool | What they do | What they miss |
|---|---|---|
| Mobalytics | General performance analytics, GPI score | Not role-specific, not live decisional |
| Porofessor | Pre-game scouting, player tendencies | Drops off in-game, data not action |
| Blitz.gg | Auto rune imports, build suggestions | Heavy ads, paywall criticism, no jungle coaching |
| U.GG overlay | In-game matchup benchmarks | No AI layer, no gank priority logic |
| iTero | AI drafting + macro coach | Newer entrant, broader scope, our niche is narrower and deeper |

The big three (Mobalytics, Porofessor, Blitz) are losing ground in 2025 due to
performance issues, creeping ad coverage, and stagnating innovation. The market is
actively looking for the next thing.

---

## Monetisation

### Plans

| Plan | Price | What you get |
|---|---|---|
| Free | €0 | Basic lane colour coding (no reasons), ads between games |
| Premium | €7.99/month | Full AI reasoning, game phase analysis, post-game breakdown |
| Pro | €18.99/month | Everything + enemy jungler prediction, win condition detector, VOD review |

### Revenue model
- Primary: recurring subscriptions via Stripe
- Secondary: non-intrusive ads on the free tier (Riot requires a free tier)
- Future: team/coach licences for amateur esports orgs, affiliate partnerships
  with LoL content creators

### Riot compliance
- Registered on the Riot Developer Portal (required to monetise)
- Free tier always exists (Riot requirement)
- Tool reads only the TAB scoreboard — information the player chooses to open
- No real-time enemy data that the player couldn't otherwise see
- Suggestions are analytical, not gameplay automation

---

## Roadmap summary

- **Phase 1** (Weeks 1–3): Python backend foundation — screen capture, OCR, matchup data
- **Phase 2** (Weeks 4–6): AI analysis engine + Electron overlay UI
- **Phase 3** (Weeks 7–9): User accounts, auth, subscription gating
- **Phase 4** (Weeks 10–12): Stripe payments, premium features, post-game breakdown
- **Phase 5** (Weeks 13–16): Polish, Riot registration, beta launch
- **Phase 6** (Month 4+): Growth, creator partnerships, expand feature set

---

## Design principles

- **Dark, sharp, data-forward**: the aesthetic of high-performance gaming tools.
  Think Mobalytics at its best, not a cheerful productivity app.
- **Never in the way**: the overlay is small, draggable, toggleable with a hotkey.
  It disappears when you don't need it.
- **Honest about uncertainty**: if the OCR fails or data is missing, say so cleanly.
  Don't show a confident suggestion based on bad data.
- **Reward the free user enough to stay, frustrate them enough to upgrade**:
  the free tier shows the priority colour but not the reason. The reason is the
  valuable part. That's the upgrade hook.

---

## Website

- Built in Next.js 14 + Tailwind + Framer Motion
- Hosted on Vercel
- Dark gaming aesthetic — not a SaaS pastel startup page
- Hero: animated overlay demo showing the three lane cards updating in real time
- Sections: How it works / Pricing / FAQ / Download
- Stripe + Supabase auth integrated directly (no separate Framer site)

---

## Things we are NOT building (for now)

- Support for other roles (we are jungle only at launch)
- Support for games other than League of Legends
- A mobile app
- A browser extension
- Anything that reads enemy data the player couldn't normally see (Riot policy)
