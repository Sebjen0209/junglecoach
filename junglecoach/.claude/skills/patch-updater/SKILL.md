---
name: patch-updater
description: Use this skill whenever a new League of Legends patch has dropped and the matchup data needs refreshing. Triggers on phrases like "new patch is out", "patch dropped", "update matchup data", "data is stale", "patch 14.X", or any mention of refreshing/updating the champion counter data or win rates. This skill knows the full workflow for scraping U.GG, validating the SQLite matchup database, and committing the updated data files. Always use this skill rather than figuring it out from scratch.
---

# Patch Updater Skill

A new LoL patch drops roughly every two weeks. This skill handles the full workflow
for refreshing JungleCoach's local matchup data cache after each patch.

## What needs updating per patch

1. `backend/data/matchups.db` — win rates per champion matchup per role
2. `backend/data/power_spikes.json` — early/mid/late strength ratings (only if Riot rebalanced a champion significantly)
3. `backend/data/champions.json` — only if a new champion was added (use champion-data-sync skill instead)

## Step 1 — identify the patch version

Ask the user which patch just dropped if they haven't said. Format: `14.6`, `14.7` etc.
Check the current patch stored in the DB:

```bash
cd backend
python -c "import sqlite3; db=sqlite3.connect('data/matchups.db'); print(db.execute('SELECT DISTINCT patch FROM matchups LIMIT 1').fetchone())"
```

## Step 2 — run the scraper

```bash
cd backend
source venv/bin/activate
python data/scraper.py --patch 14.X
```

The scraper fetches matchup win rates from U.GG for all roles and writes them to
`matchups.db`. It takes ~3-5 minutes. Expected output:

```
Fetching top lane matchups... 165 records written
Fetching mid lane matchups... 158 records written
Fetching bot lane matchups... 142 records written
Done. Patch 14.X data written to matchups.db
```

If the scraper errors, check:
- U.GG hasn't changed their page structure (most common cause)
- The user's internet connection
- Rate limiting — add a `time.sleep(2)` between requests if getting 429s

## Step 3 — validate the data

Run the validation script to catch obvious problems:

```bash
python data/validate.py
```

This checks:
- No champion has a win rate above 70% or below 30% (would indicate a scraping error)
- All 5 roles have data
- Sample sizes are above 100 games per matchup (low sample = unreliable)
- Row count is reasonable (should be 1000+ rows)

If validation fails, show the user the specific failing rows and help debug.

## Step 4 — update power_spikes.json if needed

Only needed if Riot's patch notes buffed/nerfed a champion's early/mid/late power.

Ask the user: "Were any champions significantly changed in this patch that would affect
their early/mid/late power curve?"

If yes, open `backend/data/power_spikes.json` and update the relevant champion's
`early_strength`, `mid_strength`, `late_strength` values (scale of 0.0 to 1.0).

## Step 5 — commit the update

```bash
git add backend/data/matchups.db backend/data/power_spikes.json
git commit -m "data: update matchup data for patch 14.X"
git push
```

## Step 6 — tell the user what changed

Summarise:
- How many matchup records were updated
- Which champions (if any) had power spike changes
- Whether any scraping issues were encountered

## Common issues

**U.GG page structure changed**
→ Open `data/scraper.py` and update the CSS selectors. U.GG typically changes these
once or twice per season. The win rate table is usually in a `div.champion-overview`
or similar.

**Matchup missing for a new champion**
→ New champions have low sample sizes for ~2 patches after release. The scraper will
skip them if sample_size < 100. This is intentional — unreliable data is worse than
no data. The overlay will show "Insufficient data" for that matchup.

**DB file is too large to commit**
→ If `matchups.db` exceeds 10MB, use `VACUUM` to compact it:
```bash
python -c "import sqlite3; db=sqlite3.connect('data/matchups.db'); db.execute('VACUUM'); db.commit()"
```
