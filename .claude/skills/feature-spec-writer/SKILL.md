---
name: feature-spec-writer
description: Use this skill whenever a new feature idea needs to be properly specced out and added to the project docs. Triggers on "I want to add a feature", "let's build X", "how should we design Y", "write a spec for", "plan out [feature]", or any time someone describes a new piece of functionality that needs to be thought through and documented before building. This skill produces a proper feature spec AND updates the relevant .claude files so both developers stay in sync.
---

# Feature Spec Writer Skill

Turns a rough feature idea into a proper spec, then updates the .claude project files
so both Person 1 and Person 2 know what's happening.

## Step 1 — understand the idea

Ask (or infer from context):
1. What does this feature do in one sentence?
2. Which user is it for — free or premium?
3. Is it backend (Person 1), frontend (Person 2), or both?
4. Is this Phase 1–4 (core product) or Phase 6+ (growth)?

## Step 2 — write the feature spec

Create a spec using this template:

```markdown
# Feature: [Name]

**Status**: Proposed
**Owner**: Person 1 / Person 2 / Both
**Plan tier**: Free / Premium / Pro
**Phase**: X

## What it does
One paragraph. What does the user experience?

## Why we're building it
What problem does this solve? What's the user benefit?
Reference PRODUCT.md if relevant.

## Technical approach

### Backend changes (Person 1)
- List of files to create or modify
- Any new data needed
- API changes (if any — must update api-contract.md)

### Frontend changes (Person 2)
- List of files to create or modify
- UI behaviour description
- Any new routes or components

## Acceptance criteria
- [ ] Specific, testable things that must be true for this feature to be "done"
- [ ] Each item should be verifiable by either person

## Out of scope
What are we explicitly NOT doing in this version?

## Open questions
Things that need a decision before or during build.
```

## Step 3 — update .claude files

After writing the spec, update the relevant files:

**If it touches the API contract** → add the new endpoint(s) to `api-contract.md`

**If it's primarily Person 1's work** → add tasks to the "Up next" section of `person1.md`

**If it's primarily Person 2's work** → add tasks to the "Up next" section of `person2.md`

**Always** → add an entry to `decisions.md` explaining why we're building this and any
key technical decisions made in the spec.

## Step 4 — save the spec

Save the spec as:
```
.claude/specs/[feature-name].md
```

Create the `specs/` folder if it doesn't exist.

## Step 5 — confirm with the user

Show them:
- The spec
- What files were updated
- Any open questions that need answering before building starts

Ask: "Does this look right? Anything missing or wrong before we start building?"

## Example features this skill handles well

- "I want to add an enemy jungler tracker that predicts where they are"
- "Let's build a post-game breakdown screen"
- "Add objective timer alerts for Dragon and Baron"
- "Build a win condition detector that tells you whether your team needs to end early"
- "Add a hotkey to toggle the overlay on and off"
- "Build a referral system — invite a friend gets you one month free"
