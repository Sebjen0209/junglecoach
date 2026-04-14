---
name: champion-data-sync
description: Use this skill when a new League of Legends champion is released and needs to be added to the JungleCoach data files. Triggers on "new champion released", "add [champion name] to the data", "champion not recognised", "OCR can't find champion", or any mention of a champion name that isn't in champions.json. Also use this when the OCR is failing to recognise a champion that already exists — the fix is usually adding an alias.
---

# Champion Data Sync Skill

Riot releases new champions periodically. This skill adds them to JungleCoach's
`champions.json` and sets up their initial power spike data.

## What champions.json contains

```json
{
  "champions": [
    {
      "name": "Gangplank",
      "aliases": ["Gangplsnk", "Gangpl", "GP"],
      "roles": ["top"],
      "riot_id": "Gangplank"
    }
  ]
}
```

`aliases` are alternative spellings that Tesseract OCR commonly misreads. These
are critical — without them, champion detection silently fails.

## Step 1 — fetch from Riot Data Dragon

Riot's Data Dragon API always has the latest champion list. Fetch it:

```python
import requests, json

version_url = "https://ddragon.leagueoflegends.com/api/versions.json"
latest = requests.get(version_url).json()[0]

champs_url = f"https://ddragon.leagueoflegends.com/cdn/{latest}/data/en_US/champion.json"
data = requests.get(champs_url).json()

for champ_id, champ in data["data"].items():
    print(champ_id, champ["name"])
```

## Step 2 — identify what's missing

Compare the Data Dragon list against `champions.json`:

```python
with open("backend/data/champions.json") as f:
    existing = {c["name"] for c in json.load(f)["champions"]}

missing = [name for name in data["data"] if name not in existing]
print("Missing:", missing)
```

## Step 3 — add the new champion

For each missing champion, add an entry to `champions.json`. You need to:

1. Set their likely primary role(s) — check U.GG or the Riot release page
2. Generate likely OCR aliases — Tesseract commonly confuses:
   - `rn` → `m` (e.g., "Bwain" for "Bwain")
   - `cl` → `d` 
   - `I` (capital i) → `l` (lowercase L)
   - Long names get truncated if the scoreboard clips
   - Special characters stripped (e.g., "Kai'Sa" → "KaiSa" or "Kai Sa")

3. Set initial power spike values in `power_spikes.json` — use 0.5/0.5/0.5 as
   a neutral default until real data is available after ~2 patches.

Example for a new champion "Ambessa":
```json
{
  "name": "Ambessa",
  "aliases": ["Ambess", "Ambesa", "Arnbessa"],
  "roles": ["top", "jungle"],
  "riot_id": "Ambessa"
}
```

## Step 4 — test OCR recognition

If a user reports a specific champion isn't being recognised, simulate the OCR output:

1. Ask them to screenshot the scoreboard TAB with that champion visible
2. Run pytesseract on the scoreboard region manually:
```python
import pytesseract
from PIL import Image
img = Image.open("scoreboard_screenshot.png")
print(pytesseract.image_to_string(img))
```
3. Note what Tesseract actually outputs for that name
4. Add that misread string as an alias

## Step 5 — commit

```bash
git add backend/data/champions.json backend/data/power_spikes.json
git commit -m "data: add [ChampionName] to champion data"
git push
```

## Notes

- After adding a new champion, the scraper still won't have matchup data for them
  until ~2 patches of game data accumulates. This is expected.
- If a champion is being read correctly by OCR but scoring seems wrong, the issue
  is in `power_spikes.json`, not `champions.json`.
