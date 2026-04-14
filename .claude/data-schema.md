# Data Schema

## Local SQLite database (backend/data/junglecoach.db)

Owned by Person 1. Lives on the user's machine.

```sql
-- Matchup win rates per champion pair and role
CREATE TABLE matchups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ally_champion TEXT NOT NULL,
    enemy_champion TEXT NOT NULL,
    role TEXT NOT NULL,              -- 'top' | 'mid' | 'bot' | 'support' | 'jungle'
    win_rate REAL NOT NULL,          -- 0.0 to 1.0
    sample_size INTEGER NOT NULL,    -- number of games this is based on
    patch TEXT NOT NULL,             -- e.g. '14.6'
    updated_at TEXT NOT NULL         -- ISO timestamp
);

CREATE UNIQUE INDEX idx_matchup ON matchups(ally_champion, enemy_champion, role, patch);

-- Power spike ratings per champion per game phase
CREATE TABLE power_spikes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    champion TEXT NOT NULL UNIQUE,
    early_strength REAL NOT NULL,    -- 0.0 to 1.0
    mid_strength REAL NOT NULL,
    late_strength REAL NOT NULL,
    patch TEXT NOT NULL
);
```

## Supabase Postgres (cloud)

Owned by Person 2.

```sql
-- Subscriptions
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    stripe_customer_id TEXT UNIQUE,
    stripe_subscription_id TEXT UNIQUE,
    plan TEXT DEFAULT 'free',        -- 'free' | 'premium' | 'pro'
    status TEXT DEFAULT 'active',    -- 'active' | 'cancelled' | 'past_due' | 'trialing'
    current_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Usage analytics
CREATE TABLE usage_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,        -- 'game_analysed' | 'overlay_opened' | 'subscription_started'
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Row Level Security
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users see own subscription" ON subscriptions
    FOR SELECT USING (auth.uid() = user_id);

ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users see own events" ON usage_events
    FOR SELECT USING (auth.uid() = user_id);
```

## Python data models (Pydantic)

```python
from pydantic import BaseModel
from typing import Literal

class LaneState(BaseModel):
    ally_champion: str
    enemy_champion: str
    matchup_winrate: float
    ally_phase_strength: float      # 0.0-1.0 for current game phase
    cs_diff: int                    # positive = ally ahead
    ally_kill_pressure: bool        # has ult, is level 6, etc.

class GameState(BaseModel):
    game_minute: int
    game_phase: Literal["early", "mid", "late"]
    patch: str
    top: LaneState
    mid: LaneState
    bot: LaneState

class LaneSuggestion(BaseModel):
    ally_champion: str
    enemy_champion: str
    matchup_winrate: float
    priority: Literal["high", "medium", "low"]
    reason: str
    score: float

class AnalysisResult(BaseModel):
    game_detected: bool
    game_minute: int | None
    patch: str | None
    analysed_at: str | None
    lanes: dict[str, LaneSuggestion] | None
```
