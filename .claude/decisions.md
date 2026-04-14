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

_Add new decisions below this line_
