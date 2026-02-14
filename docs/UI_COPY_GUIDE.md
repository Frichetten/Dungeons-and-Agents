# UI Copy Guide

Style guide for text inside `ui` envelopes.

## Voice

- Tactical cinematic: one short sensory line, then mechanics.
- Use plain, direct language.
- Prefer concrete values over vague summaries.

## Structure

- Keep section labels fixed to template spec.
- Write short paragraphs or compact bullet-like lines.
- Put decision-critical mechanics before flavor details.

## Terminology

Use canonical terms exactly:

- `Action`
- `Bonus Action`
- `Reaction`
- `Movement`
- `Condition`
- `Concentration`

## Transparency Rules

- Show numbers when they change decisions.
- Hide backend noise (raw internals, debug IDs, irrelevant fields).
- For high-pressure states (combat/hazards), keep flavor to one sentence max before mechanics.

## State Diff Notation

Use consistent delta style:

- `HP 18/24 (-6)`
- `Gold 42 (+10)`
- `Reputation Guard +1`
- `Spell Slots (1st) 2 (-1)`
- `Arrows 11 (-3)`

## Dialogue Choice Tags

`dialogue_turn` choices must include one tone tag:

- `firm`
- `curious`
- `deceptive`
- `empathetic`

## Prompt Rule

- Every actionable template ends with the exact prompt:
  - `What do you do?`
