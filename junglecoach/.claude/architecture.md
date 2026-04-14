# System Architecture

## High-level overview

```
┌─────────────────────────────────────────────┐
│              User's PC (local)              │
│                                             │
│  ┌──────────────┐     ┌──────────────────┐  │
│  │  LoL Game    │     │  JungleCoach     │  │
│  │  (running)   │     │  Overlay (Electron)│ │
│  └──────────────┘     └────────┬─────────┘  │
│         │ screen                │ polls      │
│         ▼ capture               │ every 5s   │
│  ┌──────────────────────────────▼─────────┐  │
│  │     Python Backend (localhost:7429)    │  │
│  │  ┌──────────┐  ┌──────────┐           │  │
│  │  │  screen  │  │ analysis │           │  │
│  │  │  capture │  │  engine  │           │  │
│  │  └──────────┘  └─────┬────┘           │  │
│  │                      │ Claude API     │  │
│  └──────────────────────┼────────────────┘  │
│                         │                   │
└─────────────────────────┼───────────────────┘
                          │ HTTPS
                          ▼
              ┌───────────────────────┐
              │   Anthropic Claude    │
              │   (claude-sonnet)     │
              └───────────────────────┘

              ┌───────────────────────┐
              │   JungleCoach Web     │
              │   (Vercel)            │
              │   - Landing page      │
              │   - Login / signup    │
              │   - Dashboard         │
              │   - Billing           │
              └──────────┬────────────┘
                         │
              ┌──────────▼────────────┐
              │   Supabase            │
              │   - Postgres DB       │
              │   - Auth              │
              └──────────┬────────────┘
                         │
              ┌──────────▼────────────┐
              │   Stripe              │
              │   - Subscriptions     │
              │   - Webhooks          │
              └───────────────────────┘
```

## Data flow — one analysis cycle

1. `screen.py` takes a screenshot every 3 seconds
2. Detects if LoL is running by window title / process name
3. If game detected: simulates TAB press, captures scoreboard region
4. `ocr.py` extracts text from scoreboard image → raw champion names
5. `champion_parser.py` fuzzy-matches names to `champions.json` → clean names + roles
6. `game_phase.py` reads the game timer from top-centre of screen → "early/mid/late"
7. `scorer.py` fetches matchup win rates from SQLite, calculates score per lane
8. `ai_client.py` builds prompt, calls Claude API, parses JSON response
9. Result stored in memory, served on `GET /analysis`
10. Overlay fetches `/analysis`, renders lane cards with colour-coded priority

## Security model

- The local backend only binds to `127.0.0.1` — not accessible from network
- Auth tokens are stored in Electron's secure storage (keytar), not localStorage
- Stripe webhooks are verified with the signing secret before processing
- Supabase Row Level Security (RLS) ensures users can only read their own data
- No game data is ever sent to our servers — all analysis is local

## Deployment

| Service | Platform | Auto-deploy |
|---|---|---|
| Web app | Vercel | Yes, on push to `main` |
| API (subscription check) | Railway | Yes, on push to `main` |
| Desktop app | GitHub Releases | Manual, on version tag |
| Supabase | Supabase cloud | Manual migrations |
