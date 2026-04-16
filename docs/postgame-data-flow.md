# Post-Game Analysis — Data Flow

How data moves from a completed LoL match to coaching feedback on the web page.

---

## System overview

```mermaid
graph TD
    Player["🎮 Player"]

    subgraph Client
        Web["Web App\n(Vercel / Next.js)"]
    end

    subgraph Cloud ["Cloud (Railway)"]
        CloudAPI["Cloud API\n(FastAPI)"]
    end

    subgraph Supabase
        Auth["Supabase Auth"]
        DB["Postgres DB\ntimeline_cache\npost_game_analyses"]
    end

    subgraph External
        Riot["Riot API\nMatch-V5"]
        Claude["Anthropic API\nClaude Sonnet"]
    end

    Player -->|"submits match ID"| Web
    Web -->|"GET /postgame/{matchId}\nBearer token"| CloudAPI
    CloudAPI -->|"validate JWT"| Auth
    Auth -->|"user_id"| CloudAPI
    CloudAPI <-->|"cache read / write\nresult persistence"| DB
    CloudAPI -->|"fetch match + timeline\n(if not cached)"| Riot
    CloudAPI -->|"coaching prompt\n(all events in one call)"| Claude
    Claude -->|"JSON feedback"| CloudAPI
    CloudAPI -->|"PostGameAnalysis"| Web
    Web -->|"coaching moments"| Player
```

---

## Request flow (sequence)

```mermaid
sequenceDiagram
    actor Player
    participant Web as Web App (Vercel)
    participant API as Cloud API (Railway)
    participant SBAuth as Supabase Auth
    participant SBDB as Supabase DB
    participant Riot as Riot API
    participant Claude as Anthropic (Claude)

    Player->>Web: Submits match ID + summoner name
    Web->>API: GET /postgame/{matchId}?summoner_name=...<br/>Authorization: Bearer <access_token>

    API->>SBAuth: get_user(token)
    SBAuth-->>API: user_id ✓

    API->>SBDB: load_existing_analysis(user_id, match_id)

    alt Analysis already exists for this user + match
        SBDB-->>API: PostGameAnalysis row
        API-->>Web: 200 PostGameAnalysis (cached, instant)
    else First time this user requests this match
        API->>SBDB: load_cached_timeline(match_id)

        alt Timeline cached (any user previously fetched this match)
            SBDB-->>API: timeline JSON (free)
        else Timeline not cached
            API->>Riot: GET /matches/{matchId}
            Riot-->>API: match summary (participants, roles)
            API->>Riot: GET /matches/{matchId}/timeline
            Riot-->>API: timeline JSON (~500 KB, frame-by-frame)
            API->>SBDB: save_cached_timeline(match_id, data)
        end

        Note over API: Parse timeline<br/>Identify jungler<br/>Classify ganks / objectives / pathing

        API->>Claude: Coaching prompt (all events, single call)
        Claude-->>API: JSON array of coaching moments

        API->>SBDB: save_analysis(user_id, PostGameAnalysis)
        API-->>Web: 200 PostGameAnalysis
    end

    Web-->>Player: Displays timestamped coaching feedback
```

---

## What each layer does

| Layer | Tech | Responsibility |
|---|---|---|
| Web app | Next.js on Vercel | UI — match ID input, display coaching moments, match history |
| Cloud API | FastAPI on Railway | Orchestration — auth, caching, Riot API, Claude, persistence |
| Supabase Auth | Supabase | JWT validation — ensures only logged-in users can trigger analysis |
| `timeline_cache` | Supabase Postgres | Shared Riot timeline cache — each match costs 1 Riot API call ever |
| `post_game_analyses` | Supabase Postgres | Per-user analysis history — idempotent, enables match history feature |
| Riot API | Match-V5 | Raw match data — participants, positions, events |
| Anthropic API | Claude Sonnet | Natural language coaching — one call per analysis, all events batched |

---

## What does NOT touch the cloud API

The local desktop backend (`localhost:7429`) handles everything that requires the user's screen:

- Screen capture (mss)
- OCR of the TAB scoreboard (pytesseract)
- Live gank priority suggestions (every ~45s during a game)

These will never move to the cloud — they are inherently local by design.
