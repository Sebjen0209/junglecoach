# Person 1 — Backend / Python / AI Engine

You are helping **Person 1** on the JungleCoach project.
Person 1 owns all Python code: screen capture, OCR, matchup data, AI analysis, and the local FastAPI server.

Read `CLAUDE.md` first for the full project context.

---

## Your current tasks (Phase 2 — AI engine)

### In progress
- [ ] Design matchup scoring algorithm
- [ ] Build game phase detector (OCR the game timer in top-centre of screen)
- [ ] Integrate Claude API for natural language suggestion output

### Up next
- [ ] Write the AI prompt (see prompt template below)
- [ ] Test AI output quality across 20+ champion combos
- [ ] Build early/mid/late power spike weighting

### Done


---

## Your ownership map

```
backend/
├── capture/
│   ├── screen.py          ← mss screenshot loop
│   ├── ocr.py             ← pytesseract wrapper + scoreboard parser
│   └── champion_parser.py ← maps text → champion names + roles
│
├── analysis/
│   ├── scorer.py          ← matchup scoring algorithm (YOUR MAIN TASK NOW)
│   ├── ai_client.py       ← Claude API integration
│   ├── game_phase.py      ← early/mid/late detection
│   └── suggestion.py      ← assembles final output for the API response
│
├── data/
│   ├── matchups.db        ← SQLite: champion counter win rates
│   ├── champions.json     ← all champion names + aliases (for OCR correction)
│   ├── power_spikes.json  ← per-champion early/mid/late strength ratings
│   └── scraper.py         ← updates matchup data from U.GG (run manually)
│
├── server.py              ← FastAPI local server on port 7429
├── main.py                ← entry point, starts capture loop + server
└── tests/
    ├── test_ocr.py
    ├── test_scorer.py
    └── test_ai_client.py
```

---

## The scoring algorithm — how it should work

The scorer takes a `GameState` object and returns a `SuggestionResult`.

### Inputs per lane
- `ally_champion` — the champion your teammate is playing
- `enemy_champion` — the champion they are against
- `matchup_winrate` — float, e.g. 0.58 means ally wins 58% of games in this matchup
- `game_phase` — "early" | "mid" | "late"
- `ally_cs_diff` — CS difference at current time (positive = ally ahead)
- `ally_kill_pressure` — bool: does ally have kill pressure right now? (e.g. has ultimate)

### Scoring formula (starting point — iterate on this)

```python
def score_lane(lane: LaneState) -> float:
    # Base: how strong is the counter advantage?
    counter_score = (lane.matchup_winrate - 0.50) * 200  # -100 to +100

    # Phase modifier: weight the counter based on when it matters
    phase_weight = {
        "early": lane.ally_champion_early_strength,
        "mid":   lane.ally_champion_mid_strength,
        "late":  lane.ally_champion_late_strength,
    }[lane.game_phase]

    # Kill pressure bonus: are they strong RIGHT NOW?
    pressure_bonus = 15 if lane.ally_kill_pressure else 0

    # CS advantage bonus: winning lane = easier gank
    cs_bonus = min(lane.ally_cs_diff * 0.5, 20)  # cap at +20

    return counter_score * phase_weight + pressure_bonus + cs_bonus
```

Score > 40 → HIGH priority (red)
Score 15–40 → MEDIUM priority (yellow)
Score < 15 → LOW priority (grey)

---

## The AI prompt template

When calling the Claude API, use this structure:

```python
SYSTEM_PROMPT = """
You are a League of Legends jungle coaching assistant.
You receive structured data about all 3 lanes and must output gank priority advice.
Be concise. Maximum 2 sentences per lane. Focus on WHY, not just the priority.
Output valid JSON only — no markdown, no explanation outside the JSON.
"""

def build_user_prompt(game_state: GameState) -> str:
    return f"""
Current game state (minute {game_state.game_minute}):

TOP: {game_state.top.ally_champion} vs {game_state.top.enemy_champion}
  - Matchup win rate for ally: {game_state.top.matchup_winrate:.0%}
  - Lane phase power: ally is {game_state.top.ally_phase_strength}/10 this phase
  - CS diff: {game_state.top.cs_diff:+d}

MID: {game_state.mid.ally_champion} vs {game_state.mid.enemy_champion}
  - Matchup win rate for ally: {game_state.mid.matchup_winrate:.0%}
  - Lane phase power: ally is {game_state.mid.ally_phase_strength}/10 this phase
  - CS diff: {game_state.mid.cs_diff:+d}

BOT: {game_state.bot.ally_champion} vs {game_state.bot.enemy_champion}
  - Matchup win rate for ally: {game_state.bot.matchup_winrate:.0%}
  - Lane phase power: ally is {game_state.bot.ally_phase_strength}/10 this phase
  - CS diff: {game_state.bot.cs_diff:+d}

Return JSON in exactly this format:
{{
  "top": {{"priority": "high|medium|low", "reason": "..."}},
  "mid": {{"priority": "high|medium|low", "reason": "..."}},
  "bot": {{"priority": "high|medium|low", "reason": "..."}}
}}
"""
```

---

## The API you expose (DO NOT change without updating api-contract.md)

`GET /analysis` — returns the latest analysis result
`GET /status` — returns capture status (is game detected, is LoL running)
`GET /health` — simple health check

Full spec in `.claude/api-contract.md`.

---

## Common issues and how to fix them

**OCR reads wrong champion name**
→ Use fuzzy matching against `champions.json`. Import `difflib.get_close_matches`.
→ The scoreboard font is fixed-width — pre-process with grayscale + threshold before OCR.

**Game not detected**
→ Check `screen.py` — it looks for the LoL window by title. On some systems the window title differs.
→ Fallback: scan for the minimap colour signature in bottom-left corner.

**Claude API too slow**
→ Cache the last response and only re-call if the game state has meaningfully changed (champion died, phase changed, 45s elapsed).
→ Use `claude-haiku` for speed during testing, switch to `claude-sonnet` for quality in prod.

**Matchup data is stale**
→ Run `python backend/data/scraper.py` to refresh from U.GG.
→ Data should be refreshed after each LoL patch (every 2 weeks).

---

## Running your code

```bash
# Setup
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Start the full backend (capture + API server)
python main.py

# Start just the API server (for testing without a game)
uvicorn server:app --reload --port 7429

# Update matchup data
python data/scraper.py
```

---

## How to ask Claude for help on this codebase

Good prompts:
- "I'm working on `scorer.py`. The scoring formula needs to weight late-game scaling champions differently. Help me refactor the `score_lane` function."
- "The OCR in `ocr.py` sometimes reads 'Gangplank' as 'Gangplsnk'. Help me add fuzzy matching."
- "Write a pytest for `ai_client.py` that mocks the Claude API response and checks the JSON parsing."

Always paste the relevant function when asking for help — Claude has no memory between sessions.
