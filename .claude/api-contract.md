# API Contract — Local Backend ↔ Overlay

**This file is the single source of truth for the API between Person 1's Python backend and Person 2's Electron overlay.**

If you need to change anything here, you MUST:
1. Update this file
2. Tell the other person before merging
3. Update both sides (backend + overlay) in the same PR

Port: `7429`
Base URL (local): `http://localhost:7429`
Protocol: HTTP REST (JSON)

---

## GET /health

Simple health check. Used by the overlay to know if the backend is running.

**Response 200**
```json
{ "status": "ok", "version": "0.1.0" }
```

---

## GET /status

Returns the current League of Legends client lifecycle phase and capture status.

**Response 200**
```json
{
  "lol_phase": "in_game",
  "lol_running": true,
  "game_detected": true,
  "capture_active": true,
  "last_capture_at": "2024-03-15T14:23:01Z"
}
```

`lol_phase` — current client phase: `"idle"` | `"client"` | `"loading"` | `"in_game"`
- `idle` — no League processes running
- `client` — client open (lobby, champion select, post-game lobby)
- `loading` — game process running, loading screen in progress
- `in_game` — active live game, analysis is running

`lol_running` — any League process is running (`lol_phase != "idle"`)
`game_detected` — secondary heuristic confirming live game via timer region brightness
`capture_active` — the capture loop is running without errors
`last_capture_at` — ISO timestamp of last successful screen read

---

## GET /analysis

Returns the latest gank priority analysis. This is the main endpoint.
The overlay polls this every 5 seconds.

**Response 200 — laning phase (all outer towers standing, < 20 min)**
```json
{
  "game_detected": true,
  "game_minute": 12,
  "patch": "14.6",
  "analysed_at": "2024-03-15T14:23:05Z",
  "analysis_mode": "laning",
  "lanes": {
    "top": {
      "ally_champion": "Riven",
      "enemy_champion": "Gangplank",
      "matchup_winrate": 0.58,
      "priority": "high",
      "reason": "Riven hard counters Gangplank pre-6. Strong kill threat right now.",
      "score": 72.4
    },
    "mid": {
      "ally_champion": "Azir",
      "enemy_champion": "Zed",
      "matchup_winrate": 0.46,
      "priority": "medium",
      "reason": "Azir is weak early but a monster late. Gank once to keep him safe.",
      "score": 28.1
    },
    "bot": {
      "ally_champion": "Jinx",
      "enemy_champion": "Caitlyn",
      "matchup_winrate": 0.51,
      "priority": "low",
      "reason": "Even matchup. Other lanes have more to offer right now.",
      "score": 8.0
    }
  },
  "macro_hints": null
}
```

**Response 200 — macro phase (any outer tower down OR ≥ 20 min)**
```json
{
  "game_detected": true,
  "game_minute": 19,
  "patch": "14.6",
  "analysed_at": "2024-03-15T14:35:12Z",
  "analysis_mode": "macro",
  "lanes": null,
  "macro_hints": [
    {
      "type": "objective",
      "urgency": "critical",
      "headline": "Dragon in 67s — tied 2-2",
      "detail": "Both teams are equal on stacks. This spawn is significant for both sides."
    },
    {
      "type": "lane",
      "urgency": "high",
      "headline": "Enemy bot lane has map freedom",
      "detail": "With their outer down, bot and support have more options. Mid may see additional presence."
    },
    {
      "type": "objective",
      "urgency": "medium",
      "headline": "Baron comes online in ~90s",
      "detail": "Teams typically begin baron-related decisions 2 minutes before spawn."
    }
  ]
}
```

**Response 200 — no game detected**
```json
{
  "game_detected": false,
  "game_minute": null,
  "patch": null,
  "analysed_at": null,
  "analysis_mode": null,
  "lanes": null,
  "macro_hints": null
}
```

### Field definitions

| Field | Type | Description |
|---|---|---|
| `game_detected` | bool | Is a live game in progress |
| `game_minute` | int \| null | Current game minute |
| `patch` | string \| null | Current patch version |
| `analysed_at` | ISO string \| null | When the analysis was last run |
| `analysis_mode` | `"laning"` \| `"macro"` \| null | Which mode is active. Overlay should branch on this. |
| `lanes` | object \| null | Populated in laning mode only |
| `lanes.{lane}.ally_champion` | string | Ally champion name |
| `lanes.{lane}.enemy_champion` | string | Enemy champion name |
| `lanes.{lane}.matchup_winrate` | float | 0.0–1.0, ally win rate in this matchup |
| `lanes.{lane}.priority` | string | `"high"` \| `"medium"` \| `"low"` |
| `lanes.{lane}.reason` | string \| null | 1–2 sentence explanation (null for free users) |
| `lanes.{lane}.score` | float | Raw score (for debugging) |
| `macro_hints` | array \| null | Populated in macro mode, premium only. null for free users or laning mode. |
| `macro_hints[].type` | string | `"objective"` \| `"lane"` \| `"trade"` \| `"state"` |
| `macro_hints[].urgency` | string | `"critical"` \| `"high"` \| `"medium"` |
| `macro_hints[].headline` | string | Short bold text for the overlay card (≤ 8 words) |
| `macro_hints[].detail` | string | 2 sentences of context |

### Overlay rendering guide

```
if analysis_mode == "laning":
    render lane cards (existing behaviour)
elif analysis_mode == "macro":
    if macro_hints is null or empty:
        render "Macro phase — upgrade for awareness hints" (free upsell)
    else:
        render MacroHint cards (urgency colour, headline bold, detail below)
```

Urgency colours (suggestion):
- `critical` → red / pulsing
- `high` → orange
- `medium` → grey / dim

---

## GET /subscription

Checks if the current user has an active premium subscription.
The overlay calls this on startup using the stored auth token.

**Headers**
```
Authorization: Bearer <jwt_token>
```

**Response 200**
```json
{
  "plan": "premium",
  "valid": true,
  "expires_at": "2024-04-15T00:00:00Z"
}
```

**Response 401** — missing or invalid token
```json
{ "error": "unauthorized" }
```

**Response 200 — free user**
```json
{
  "plan": "free",
  "valid": true,
  "expires_at": null
}
```

---

## Error responses

All errors follow this shape:
```json
{
  "error": "short_error_code",
  "message": "Human readable description"
}
```

Common error codes:
- `ocr_failed` — could not read the scoreboard
- `ai_timeout` — Claude API took too long
- `champion_not_found` — OCR returned a name not in champions.json
- `no_data` — matchup data missing for this combination

---

## Version history

| Version | Date | Change |
|---|---|---|
| 0.1.0 | 2024-03-01 | Initial contract |
| 0.2.0 | 2026-04-15 | `/status` — added `lol_phase` field; overlay should use this instead of `lol_running` for UI state |
| 0.3.0 | 2026-04-23 | `/analysis` — added `analysis_mode` and `macro_hints` fields. Overlay must branch on `analysis_mode`. New `POST /analysis/macro` on Railway (internal, called by backend). |

When you bump the version, add a row here and update both sides.
