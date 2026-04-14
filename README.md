# JungleCoach

Real-time League of Legends jungler assistant. Reads your game screen, analyses champion matchups, and tells you where to gank and why.

## Quick start

**Person 1 (backend):**
```bash
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py
```

**Person 2 (overlay + web):**
```bash
cd overlay && npm install && npm run dev
cd web && npm install && npm run dev
```

## Docs
- `.claude/CLAUDE.md` — full project context for Claude
- `.claude/person1.md` — Person 1 task list and backend guide
- `.claude/person2.md` — Person 2 task list and frontend guide
- `.claude/api-contract.md` — the shared API spec between backend and overlay
- `.claude/architecture.md` — system architecture overview
- `.claude/data-schema.md` — all data models
- `.claude/decisions.md` — log of key technical decisions

## How to use Claude on this project

Open Claude, start a new conversation, and paste:

> "Read `.claude/CLAUDE.md` and `.claude/person1.md` [or person2.md]. I'm working on [describe what you're building]. Here's the relevant code: [paste it]."

Claude will have full project context and give you accurate, on-spec help.
