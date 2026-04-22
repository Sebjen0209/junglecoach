# Person 1 — Backend / Python / AI Engine

You are helping **Person 1** on the JungleCoach project.
Person 1 owns all Python code: Riot Live Client API integration, matchup data, AI analysis, and the local FastAPI server.

Read `CLAUDE.md` first for the full project context.

---

## Current status (as of 2026-04-21)

### Completed ✅
- Live Client API integration (replaced OCR + screen capture entirely)
- Matchup scoring algorithm (`analysis/scorer.py`)
- Game phase detection from game time (`analysis/game_phase.py`)
- Claude AI integration + prompts (`analysis/ai_client.py`)
- Kill pressure signals (ignite, level 6+, kill lead)
- CS diff tracking
- Experience modifier (`analysis/experience.py`) — uses Riot mastery API
- Post-game analysis endpoint (`/postgame/{match_id}`)
- Cloud API deployed on Railway (`https://junglecoach-production.up.railway.app`)
- Matchup DB seeded with real U.GG data — 143,844 rows, patch 16.8
- Patch update pipeline (local scrape → upload to Supabase Storage → notify Railway)
- All Supabase tables created (timeline_cache, post_game_analyses, data_versions)
- GitHub Actions patch-check workflow (runs every 2 hours, alerts on new patch)

### In progress 🔄
- Seeding the online DB: upload script works (switched from httpx to requests),
  but cloud API POST /data/versions returns 500.
  **Most likely cause: `data_versions` table not created in Supabase yet.**
  Fix: go to Supabase SQL editor and run:
  ```sql
  create table data_versions (
      patch      text primary key,
      db_url     text not null,
      row_count  int  not null,
      scraped_at timestamptz default now()
  );
  ```
  Then re-run: `bash scripts/upload_local.sh 16.8`
  Verify: `https://junglecoach-production.up.railway.app/data/latest`

---

## What's left for Person 1 (priority order)

### 1. Fix the upload 500 error (5 minutes)
See "In progress" above. Create the `data_versions` table in Supabase then re-run the upload script.

### 2. Test the backend end-to-end (most important)
The Live Client migration has never been tested in a real game.
- Open a Practice Tool game
- Start the backend: `cd backend && uvicorn server:app --port 7429`
- Hit `http://localhost:7429/analysis` and verify it returns real data
- This will likely surface bugs

### 3. Subscription check in the backend
`/subscription` is currently a stub returning `free` for everyone.
It needs to call the cloud API to verify the user has an active Stripe subscription
before returning analysis results.

### 4. Desktop packaging (wait for Person 2)
Bundle the Python backend into a `.exe` with PyInstaller.
**Wait until Person 2 has the Electron overlay working** — the installer bundles both together.

---

## How patch updates work (manual process)

U.GG blocks GitHub Actions IPs via Cloudflare, so scraping must be done locally.
Every ~2 weeks when a new patch drops:

```bash
# 1. Scrape U.GG locally (~10 min)
cd backend
python -m data.scraper --patch=X.X

# 2. Upload to Supabase + notify Railway
cd ..
bash scripts/upload_local.sh X.X
```

GitHub Actions checks for new patches every 2 hours and fails visibly when one is detected — that's your alert.
`scripts/upload_local.sh` contains the real credentials and is gitignored.

---

## Ownership map

```
backend/
├── capture/
│   ├── live_client.py     ← Riot Live Client API (localhost:2999)
│   └── screen.py          ← lightweight phase monitor only (no screenshots)
│
├── analysis/
│   ├── scorer.py          ← matchup scoring algorithm
│   ├── ai_client.py       ← Claude API integration
│   ├── game_phase.py      ← early/mid/late detection from game time
│   ├── experience.py      ← mastery/rank experience modifier
│   ├── suggestion.py      ← assembles final output
│   └── postgame/          ← post-game coaching via Riot Match-V5
│
├── data/
│   ├── junglecoach.db     ← SQLite: 143,844 matchup rows (patch 16.8, real data)
│   ├── champions.json     ← all champion names + aliases
│   ├── power_spikes.json  ← per-champion early/mid/late strength ratings
│   ├── scraper.py         ← U.GG scraper (run locally, not in CI)
│   ├── updater.py         ← startup patch check (downloads new DB from cloud)
│   └── riot_api.py        ← Riot remote API client (mastery, match history)
│
├── server.py              ← FastAPI local server on port 7429
├── config.py              ← settings (reads from .env)
├── models.py              ← shared Pydantic models
└── tests/                 ← 49+ tests passing

cloud_api/                 ← deployed on Railway
├── main.py                ← FastAPI app, production hardened
├── routers/
│   ├── postgame.py        ← /postgame/{match_id}
│   └── data.py            ← /data/latest, /data/versions
├── db/
│   ├── supabase.py        ← Supabase client + timeline cache + analysis persistence
│   └── patch.py           ← data_versions table operations
└── config.py

scripts/
├── upload_local.sh        ← gitignored, contains secrets, run after each scrape
├── upload_matchups.py     ← uploads DB to Supabase Storage + notifies Railway
└── check_patch.py         ← CI patch version checker
```

---

## Environment variables

`backend/.env`:
```
ANTHROPIC_API_KEY=...
RIOT_API_KEY=...
RIOT_PLATFORM=euw1
RIOT_REGION=europe
DB_PATH=./data/junglecoach.db
LOG_LEVEL=INFO
AI_MODEL=claude-haiku-4-5-20251001
CURRENT_PATCH=16.8
CLOUD_API_URL=https://junglecoach-production.up.railway.app
```

Railway variables (cloud_api): ANTHROPIC_API_KEY, RIOT_API_KEY, SUPABASE_URL,
SUPABASE_SERVICE_ROLE_KEY, SCRAPER_SECRET, ENVIRONMENT, LOG_LEVEL, ALLOWED_ORIGINS

---

## Running the backend

```bash
cd backend
source venv/Scripts/activate   # Windows Git Bash
uvicorn server:app --reload --port 7429
```

API endpoints:
- `GET /health` — health check
- `GET /status` — is game detected, is LoL running
- `GET /analysis` — latest gank suggestions (main endpoint)
- `GET /postgame/{match_id}` — post-game coaching
- `GET /subscription` — stub, returns free (not yet implemented)
