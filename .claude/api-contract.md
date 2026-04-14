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

Returns whether a LoL game is currently detected on screen.

**Response 200**
```json
{
  "lol_running": true,
  "game_detected": true,
  "capture_active": true,
  "last_capture_at": "2024-03-15T14:23:01Z"
}
```

`lol_running` — League of Legends process is running
`game_detected` — a live game is in progress (vs lobby/champion select)
`capture_active` — the capture loop is running without errors
`last_capture_at` — ISO timestamp of last successful screen read

---

## GET /analysis

Returns the latest gank priority analysis. This is the main endpoint.
The overlay polls this every 5 seconds.

**Response 200 — game in progress**
```json
{
  "game_detected": true,
  "game_minute": 12,
  "patch": "14.6",
  "analysed_at": "2024-03-15T14:23:05Z",
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
      "reason": "Azir is weak early but a monster late. Gank once to keep him safe — +30% win rate if ahead at 20 min.",
      "score": 28.1
    },
    "bot": {
      "ally_champion": "Jinx",
      "enemy_champion": "Caitlyn",
      "matchup_winrate": 0.51,
      "priority": "low",
      "reason": "Even matchup. Spend time elsewhere unless they push hard.",
      "score": 8.0
    }
  }
}
```

**Response 200 — no game detected**
```json
{
  "game_detected": false,
  "game_minute": null,
  "patch": null,
  "analysed_at": null,
  "lanes": null
}
```

### Field definitions

| Field | Type | Description |
|---|---|---|
| `game_detected` | bool | Is a live game in progress |
| `game_minute` | int \| null | Estimated game minute from OCR |
| `patch` | string \| null | Current patch version |
| `analysed_at` | ISO string \| null | When the analysis was last run |
| `lanes.{lane}.ally_champion` | string | Ally champion name (exact, from champions.json) |
| `lanes.{lane}.enemy_champion` | string | Enemy champion name |
| `lanes.{lane}.matchup_winrate` | float | 0.0–1.0, ally's win rate in this matchup |
| `lanes.{lane}.priority` | string | `"high"` \| `"medium"` \| `"low"` |
| `lanes.{lane}.reason` | string | 1–2 sentence natural language explanation |
| `lanes.{lane}.score` | float | Raw internal score (for debugging) |

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

When you bump the version, add a row here and update both sides.
