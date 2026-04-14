# JungleCoach — Claude Project Intelligence

You are working on **JungleCoach**, a real-time League of Legends jungler assistant.
It reads the game screen via OCR, analyses champion matchups using live data, and
displays AI-powered gank priority suggestions as an overlay during the game.

---

## What this product does

1. Captures the user's screen every ~3 seconds while LoL is running
2. OCRs the TAB scoreboard to detect all 10 champions and their roles
3. Pulls win-rate and matchup data from a local cache (sourced from U.GG / LoLalytics)
4. Feeds matchup data + game phase into an AI model
5. Outputs a ranked gank priority suggestion per lane with natural language reasoning
6. Displays the output as a lightweight overlay window on top of the game

---

## Repo structure

```
junglecoach/
├── .claude/              ← YOU ARE HERE — all Claude context lives here
│   ├── CLAUDE.md         ← main project brief (this file)
│   ├── person1.md        ← Person 1 context (backend / Python / AI)
│   ├── person2.md        ← Person 2 context (frontend / web / payments)
│   ├── architecture.md   ← full system architecture reference
│   ├── api-contract.md   ← the WebSocket API between Python engine and overlay
│   ├── data-schema.md    ← database schema and data models
│   └── decisions.md      ← log of key technical decisions made
│
├── backend/              ← Python — owned by Person 1
│   ├── capture/          ← screen capture and OCR
│   ├── analysis/         ← matchup scoring and AI integration
│   ├── data/             ← local champion/matchup data cache
│   └── tests/
│
├── overlay/              ← Electron or PyQt overlay app — shared
│
├── web/                  ← Next.js web app — owned by Person 2
│   ├── src/
│   └── public/
│
├── scripts/              ← shared dev scripts (setup, seed data, etc.)
├── docs/                 ← public documentation
└── .github/workflows/    ← CI/CD pipelines
```

---

## Tech stack

| Layer | Technology | Owner |
|---|---|---|
| Screen capture | Python + `mss` | Person 1 |
| OCR | `pytesseract` + Tesseract | Person 1 |
| Matchup data | SQLite cache + scraper | Person 1 |
| AI suggestions | Anthropic Claude API | Person 1 |
| Game phase detection | OCR of game timer | Person 1 |
| Overlay UI | Electron (HTML/CSS/JS) | Person 2 |
| Backend API | FastAPI (Python) | Person 1 |
| Web app | Next.js 14 + Tailwind | Person 2 |
| Auth | Supabase Auth | Person 2 |
| Database | Postgres via Supabase | Person 2 |
| Payments | Stripe | Person 2 |
| Hosting | Railway (API) + Vercel (web) | Person 2 |
| Error tracking | Sentry | Both |

---

## Key integration point — the API contract

The Python backend runs a local FastAPI server on `http://localhost:7429`.
The Electron overlay polls this every 5 seconds for the latest analysis.

**See `.claude/api-contract.md` for the full spec.**

The two developers must NOT change this contract without telling each other.
If you need to modify it, update `api-contract.md` and flag it clearly in a PR.

---

## Environment variables

Backend (`.env` in `/backend`):
```
ANTHROPIC_API_KEY=
RIOT_API_KEY=
DB_PATH=./data/junglecoach.db
LOG_LEVEL=INFO
```

Web (`.env.local` in `/web`):
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=
NEXT_PUBLIC_API_URL=http://localhost:7429
```

Never commit `.env` files. They are in `.gitignore`.

---

## Coding standards

- Python: black formatter, ruff linter, type hints on all functions, docstrings on all classes
- TypeScript: strict mode on, ESLint + Prettier, no `any` types
- All functions should be small and single-purpose
- Every new feature needs at least one test
- PR reviews are required before merging to `main`
- Branch naming: `p1/feature-name` for Person 1, `p2/feature-name` for Person 2

---

## Riot compliance rules (IMPORTANT)

- The tool is registered on the Riot Developer Portal as required
- It must NOT read live game data that provides real-time enemy information not visible to the player (e.g. exact enemy positions, hidden cooldowns)
- It reads only the TAB scoreboard (which the player opens themselves)
- Suggestions are analytical, not real-time gameplay automation
- Free tier must always exist — Riot requires it
- If in doubt: read `.claude/decisions.md` for the compliance decision log

---

## Current phase

**Phase 2 — AI analysis engine** (Weeks 4–6)

Person 1 is building the matchup scoring algorithm and Claude API integration.
Person 2 is building the Electron overlay shell and connecting it to the local API.

See `person1.md` and `person2.md` for detailed current task lists.
