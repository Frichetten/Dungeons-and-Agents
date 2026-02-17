# UI Copy Guide

Style guide for text inside `ui` envelopes.

## Voice

- Tactical cinematic: one short sensory line, then decision-critical details.
- Use plain, direct language.
- Prefer concrete values over vague summaries.
- Keep Scene and Outcome warm and narrative, not sterile status readouts.

## Structure

- Keep section labels fixed to template spec.
- Write short, connected paragraphs for Scene and Outcome.
- Put decision-critical details before flavor details.

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
- For high-pressure states (combat/hazards), keep flavor to one sentence max before critical details.

## Combat Options Line

- In `combat_turn`, use one compact options line for PC turns only.
- Format as: `Options: <Action/Bonus/Reaction/Move>; Slots <compact slots>; Spells <up to 3 names> (+N)`
- Keep it to one line and place it in `Scene` after turn context.

## Delta Notation

Use consistent delta style:

- `HP 18/24 (-6)`
- `Gold 42 (+10)`
- `Reputation Guard +1`
- `Spell Slots (1st) 2 (-1)`
- `Arrows 11 (-3)`

## Prompt Rule

- Every actionable template ends with the exact prompt:
  - `What do you do?`
