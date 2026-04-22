# Decision Log

A running log of significant technical and product decisions.
Add a new entry whenever you make a choice that affects the other person or the overall architecture.

Format:
```
## YYYY-MM-DD — Short title
**Decision**: What was decided
**Why**: The reason
**Alternatives considered**: What else was on the table
**Impact**: Who/what is affected
```

---

## 2024-03-01 — Use OCR over Riot API for live game data

**Decision**: Read game state via screen OCR (pytesseract on the TAB scoreboard) rather than the Riot Live Game API.

**Why**: The Riot Live Game API has ~30-60 second delay and does not provide real-time in-game state during a match. OCR gives us near-real-time data. Also avoids API rate limits.

**Alternatives considered**: Riot Live Game Client API (localhost:2999) — this IS real-time and worth revisiting. It exposes champion names, scores, and game time. May replace OCR in Phase 3.

**Impact**: Person 1 — OCR is more fragile than an API. Must handle patch-to-patch UI changes.

---

## 2024-03-01 — Port 7429 for local backend

**Decision**: Python FastAPI backend binds to localhost:7429.

**Why**: Unlikely to conflict with other common dev ports (3000, 5432, 8080 etc.). Memorable (7-4-2-9 → "J-A-I-L" if you squint).

**Alternatives considered**: 8000 (too common), 3001 (conflicts with some React setups).

**Impact**: Both — this is hardcoded in the API contract. Do not change without updating both sides.

---

## 2024-03-01 — Electron for overlay, not PyQt

**Decision**: Build the overlay in Electron (HTML/CSS/JS) rather than PyQt or tkinter.

**Why**: Person 2 is stronger in frontend web tech. Electron gives full CSS control for the overlay design. Easier to style semi-transparent always-on-top windows.

**Alternatives considered**: PyQt5 (Person 1 could own it, but weaker design control), tkinter (too limited), Tauri (faster/lighter but Rust learning curve).

**Impact**: Person 2 owns the overlay. Adds ~100MB to download size (Electron runtime). Acceptable.

---

## 2024-03-01 — Supabase for auth and database

**Decision**: Use Supabase (hosted Postgres + Auth) rather than rolling our own auth.

**Why**: Saves weeks of auth work. Row Level Security built in. Free tier sufficient for launch. Generous limits before paid tier kicks in.

**Alternatives considered**: Firebase (less control, NoSQL), PlanetScale (MySQL only), self-hosted Postgres (more ops work).

**Impact**: Person 2 — all DB work goes through Supabase client/admin SDK.

---

## 2024-03-01 — claude-haiku for dev, claude-sonnet for prod

**Decision**: Use `claude-haiku-4-5-20251001` during development and testing. Switch to `claude-sonnet-4-6` in production.

**Why**: Haiku is ~20x cheaper and faster — fine for testing prompt quality. Sonnet gives better reasoning quality for the actual suggestions users pay for.

**Alternatives considered**: GPT-4o (comparable quality but we're already on Anthropic stack), local LLM (too slow for real-time use).

**Impact**: Person 1 — set via env var `AI_MODEL`. Default to haiku in dev, sonnet in prod.

---

## 2026-04-14 — Matchup data distributed via CDN, not scraped by clients

**Decision**: `scraper.py` is an internal dev tool only. Developers run it after each patch and upload a pre-built `matchups.db` (or JSON export) to a CDN/Railway endpoint. Clients download fresh data on startup if their local patch version is outdated.

**Why**: Having every client independently scrape U.GG would (a) get our users IP-banned, (b) be slow as a first-run experience, and (c) produce inconsistent data. Centralising the scrape gives us one controlled, validated dataset per patch.

**Alternatives considered**:
- Client-side scrape on install (fragile, ToS risk for users)
- Bundle `matchups.db` in every installer update (forces a full re-download every 2 weeks just for data)
- Use Riot's official API for matchup stats (doesn't expose aggregated win-rate data)

**Impact**: Person 1 — needs to build a `/data/latest` endpoint on Railway that returns the current patch version + a signed CDN URL for the `matchups.db` download. Client backend checks this on startup and re-downloads if stale. Person 2 — Railway service needs a new route.

---

## 2026-04-14 — AI calls are per-user, billed to the product (not the user)

**Decision**: The `ANTHROPIC_API_KEY` lives in the backend that runs on the user's machine. In production this key will be tied to our Anthropic account, not the user's. The cost is borne by the product and factored into subscription pricing.

**Why**: Requiring users to supply their own API key creates friction and makes the free tier impossible. Controlling the key also lets us rate-limit free users (scorer-only, no AI) vs premium users (full AI reasons).

**Alternatives considered**: User-supplied API key (too much friction), running the AI call server-side on Railway (adds latency, more complex, but worth revisiting if key security becomes a concern).

**Impact**: Person 1 — the API key must NOT be hard-coded or committed. It will be injected at install time (TBD — possibly fetched from Railway on first auth). For now, dev uses a personal key in `.env`. Person 2 — free vs premium feature gating needs to suppress the AI call for free users (return scorer-only result).

---

## 2026-04-16 — Post-game analysis runs on Railway (cloud), not the local backend

**Decision**: The `analysis/postgame/` module will be deployed to the Railway cloud API, not served from the local `localhost:7429` backend. The Next.js web app will call Railway directly for post-game coaching results.

**Why**: Post-game analysis has no dependency on the local machine — it only needs a match ID, the Riot API, and the Anthropic API. Unlike live analysis (which requires screen capture and OCR), this feature works equally well server-side. Moving it to Railway means users can access their coaching feedback from the web page without the desktop app running, and results can be persisted to Supabase as a game history.

**Alternatives considered**: Keep it on the local backend and have the Electron overlay show a post-game screen (simpler short-term, but results are lost when the app closes and the web page can't access them independently).

**Impact**:
- Person 1 — `analysis/postgame/` is already written to be stateless and portable. It needs to be mounted in the Railway FastAPI app. `RIOT_API_KEY` and `ANTHROPIC_API_KEY` must be added as Railway env vars. The disk-based timeline cache should be replaced with a Supabase/Redis cache in the cloud version.
- Person 2 — Railway needs a new `GET /postgame/{match_id}` route. The web app UI should let users submit a match ID and display the `CoachingMoment` list. Persisting results to a `post_game_analyses` Supabase table is a natural extension and enables a match history feature (good premium upsell).

## 2026-04-16 — cloud_api/ service built and architecture locked

**Decision**: Created `cloud_api/` as a self-contained Railway-deployable FastAPI service. It is separate from `backend/` (the local desktop app) and has no screen-capture dependencies. See `docs/postgame-data-flow.md` for the full architecture diagram.

**Key implementation choices made**:
- **Supabase timeline cache** — raw Riot timeline JSON is stored in `timeline_cache` (JSONB). The first user to request a given match pays the Riot API call; all subsequent requests for that match (by any user) are free. The cache never expires — timelines are immutable.
- **Idempotency on analysis** — if a user re-requests analysis for a match they've already seen, the persisted result is returned from `post_game_analyses` instantly. No Riot API call, no Claude API call.
- **JWT auth via Supabase** — `Authorization: Bearer <supabase_access_token>` validated server-side by calling `supabase.auth.get_user()`. No JWT secret management needed on our end.
- **Region auto-detection** — platform and regional routing are inferred from the match ID prefix (e.g. `EUW1_` → `euw1` / `europe`). No user configuration required.
- **Fail-fast startup** — missing env vars cause the process to exit at startup, not at first request.
- **Docs-disabled in production** — `/docs` and `/openapi.json` are disabled when `ENVIRONMENT=production`.

**Impact**:
- Person 1 — deploy `cloud_api/` to Railway as a new service (separate from any existing services). Set the 5 required env vars. See `.env.example` inside `cloud_api/`.
- Person 2 — run the two Supabase SQL migrations (in `cloud_api/db/supabase.py` docstring). Call `GET /postgame/{matchId}` with the user's Bearer token. Add `NEXT_PUBLIC_CLOUD_API_URL` to Vercel env vars.

---

## 2026-04-15 — Replace OCR pipeline with Riot Live Client Data API

**Decision**: The main data pipeline now reads champion names, CS, kills, and
game time directly from the Riot Live Client Data API (`https://127.0.0.1:2999`)
instead of via screen capture and OCR.

**Why**: OCR required the player to hold TAB open to get champion names — poor
UX and fundamentally wrong. Champions are fixed after champion select and don't
need re-reading. What actually changes during a game (CS, kills, game time) was
*not* being tracked at all. The Live Client API is Riot's official local API for
exactly this use case: it provides real-time structured data, requires no player
interaction, and only exposes information already visible to the player.

**What changed**:
- `capture/live_client.py` (new) — fetches `/liveclientdata/allgamedata` every
  request cycle; produces a `GameSnapshot` with all 10 players' champions,
  positions, CS, kills, and game time.
- `capture/screen.py` (simplified) — stripped to a lightweight phase monitor;
  no longer does any screen capture or image processing.
- `analysis/game_phase.py` — added `game_time_to_phase(seconds)` as the primary
  path; the OCR-based `detect_game_phase()` is kept for offline dev/testing only.
- `analysis/suggestion.py` — `analyse()` now takes a `GameSnapshot` instead of
  a `ScoreboardOCRResult`; CS diffs are fed from live data automatically.
- `server.py` — `/analysis` calls `get_snapshot()` directly; no OCR in the path.
- `requirements.txt` — removed `mss` and `pywin32` (no longer needed).
- `ocr.py` and `champion_parser.py` retained as-is (tests still pass; useful for
  debugging and any future screenshot-based work).

**Riot compliance**: The Live Client Data API is documented and explicitly
permitted for third-party tools. It exposes only player-visible data — no
fog-of-war information, no hidden cooldowns. This is strictly more compliant
than the previous OCR approach (which could theoretically be extended to read
anything on screen). Reference: developer.riotgames.com/docs/lol#game-client-api

**Alternatives considered**: Keeping OCR as a fallback (rejected — adds
complexity with no benefit; the API is more reliable in every dimension).

**Impact**: Person 1 — main data pipeline is now Live Client API only. OCR
modules are deprioritised but not deleted. Person 2 — no change to the API
contract or overlay.

---

## 2026-04-21 — U.GG scraper is local-only; CI only checks for new patches

**Decision**: The U.GG scraper (`data/scraper.py`) and the upload script (`scripts/upload_local.sh`) are run manually on a developer machine after each patch. The GitHub Actions workflow (`check_patch.yml`) only *detects* new patches and fails visibly as an alert — it never scrapes or uploads.

**Why**: U.GG blocks GitHub Actions runner IPs via Cloudflare. Any attempt to scrape from CI produces a 403. Running it locally also lets us validate the scraped data before uploading to production.

**Alternatives considered**: Rotating proxies or a self-hosted runner (too much ops overhead for a 2-week scrape cadence).

**Impact**: Person 1 — patch updates are a manual 2-step local process: `python -m data.scraper --patch=X.X` then `bash scripts/upload_local.sh X.X`. `upload_local.sh` is gitignored (contains credentials). Person 2 — no change.

---

## 2026-04-21 — Use `requests` (not `httpx`) for Supabase Storage uploads

**Decision**: `scripts/upload_matchups.py` uses the `requests` library for the multipart upload to Supabase Storage, not `httpx`.

**Why**: `httpx` defaults to HTTP/2, which caused connection errors with Supabase Storage during upload testing. Switching to `requests` (HTTP/1.1) resolved the issue immediately.

**Alternatives considered**: Forcing `httpx` to HTTP/1.1 via `http2=False` (viable but adds a config trap for future maintainers; `requests` is simpler and has no HTTP/2 ambiguity).

**Impact**: Person 1 — `requests` must be in `requirements.txt` for the scripts environment. Do not refactor the upload script to use `httpx` without testing HTTP/2 compatibility first.

---

## 2026-04-22 — Move Claude API call to Railway; no secrets on the user's machine

**Decision**: The Anthropic API call is made by the Railway cloud API (`POST /analysis/reasons`), not the local backend. The local backend POSTs the `GameState` to Railway and receives reasoning strings back. The `ANTHROPIC_API_KEY` is removed from `backend/config.py` and the local `.env` entirely.

**Why**: Any secret stored on an end user's machine can be extracted — PyInstaller `.exe` files can be decompiled, `.env` files can be read. There is no safe way to ship a billing API key to hardware you don't control. Moving the call to Railway means the key lives only in Railway environment variables, which only the team can access. A compromised key can be rotated in one place with no installer update required.

**What changed**:
- `cloud_api/routers/analysis.py` (new) — `POST /analysis/reasons`: validates Supabase JWT, checks subscription tier, returns null reasons for free users, calls Claude for premium/pro.
- `backend/analysis/ai_client.py` — replaced Anthropic client with `httpx.post()` to Railway. Caching logic (45s min interval, state-diff check) is unchanged.
- `backend/analysis/suggestion.py` — `analyse()` accepts `jwt` param, passes it to `ai_client.get_reasons()`.
- `backend/server.py` — extracts `Authorization: Bearer` header from overlay requests, forwards JWT to `analyse()`.
- `backend/config.py` — removed `ANTHROPIC_API_KEY` and `AI_MODEL` fields.
- `backend/models.py` — `LaneSuggestion.reason` changed to `str | None` (free users get null).
- `overlay/renderer/overlay.js` — `fetchAnalysis()` now passes `Authorization: Bearer <jwt>` header to the local backend.

**Alternatives considered**: Fetching a short-lived proxy token from Railway on app startup (complex, still lands a token on disk). User-supplied API key (too much friction, kills free tier).

**Impact**:
- Person 1 — remove `ANTHROPIC_API_KEY` from `backend/.env`. Add `CLOUD_API_URL` if not already present. Railway already has the key.
- Person 2 — no overlay or web changes required. The overlay `reason` field can now be null; the existing null-check in `renderLanes()` already handles this correctly.

---

_Add new decisions below this line_
