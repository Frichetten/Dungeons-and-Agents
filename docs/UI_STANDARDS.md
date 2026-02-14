# Unified Game UI Standard v1

This document defines the strict player-facing UI contract used by runtime responses.

## Contract Goals

- Use one chat-first envelope for all player-facing output.
- Keep tactical-cinematic tone: one short flavor line, then decision-critical mechanics.
- Use four default choices plus a freeform fallback on actionable templates.
- Enforce section order, section labels, and prompt consistency.

## Canonical Envelope

Every UI envelope uses this key order:

1. `ui_contract_version`
2. `template_id`
3. `title`
4. `sections`
5. `choices`
6. `freeform_hint`
7. `prompt`

Version is fixed at `1.0`.

```json
{
  "ui_contract_version": "1.0",
  "template_id": "combat_turn",
  "title": "Round 2 - Arin's Turn",
  "sections": [
    {"id":"scene","label":"Scene","content":"..."},
    {"id":"mechanics","label":"Mechanics","content":"..."},
    {"id":"rolls","label":"Rolls","content":"..."},
    {"id":"outcome","label":"Outcome","content":"..."}
  ],
  "choices": [
    {"id":"1","label":"Strike the raider","intent":"Action","risk":"Medium"},
    {"id":"2","label":"Disengage to cover","intent":"Action+Move","risk":"Low"},
    {"id":"3","label":"Drink potion","intent":"Bonus","risk":"Low"},
    {"id":"4","label":"Help ally flank","intent":"Action","risk":"Medium"}
  ],
  "freeform_hint":"Or describe another action.",
  "prompt":"What do you do?"
}
```

## Template Registry

- `scene_turn`
  - Sections: `scene`, `mechanics`, `outcome`
- `dialogue_turn`
  - Sections: `scene`, `mechanics`, `outcome`
  - Choice tone tags required: `firm`, `curious`, `deceptive`, `empathetic`
- `combat_turn`
  - Sections: `scene`, `mechanics`, `rolls`, `outcome`
- `exploration_turn`
  - Sections: `scene`, `mechanics`, `outcome`
- `skill_check_turn`
  - Sections: `scene`, `mechanics`, `rolls`, `outcome`
- `ooc_panel`
  - Sections: `overview`, `resources`, `objectives`, `world`
  - Non-actionable: no choices, no prompt
- `system_error`
  - Sections: `error`, `rollback`, `recovery`

## Choice Grammar

Input resolution rules:

1. Numbered choice (`1`, `2`, `3`, `4`)
2. Exact label match
3. Freeform fallback

Rendering rules:

- Choices are always rendered as numbered lines (`1.` to `4.`).
- Actionable templates always include:
  - `freeform_hint`: `Or describe another action.`
  - `prompt`: `What do you do?`
- Player-facing markdown should not print envelope metadata lines (`ui_contract_version`, `template_id`).

## Validation Rules

The validator rejects envelopes when:

- Required keys are missing or out of canonical order.
- `template_id` is unknown.
- Required sections are missing, mislabeled, or out of order.
- Actionable templates do not have exactly 4 choices.
- Choice IDs are not sequential (`1` to `4`).
- Actionable prompt is not exactly `What do you do?`.

## Runtime Integration

Current runtime integration points in `tools/dmctl`:

- `combat start`, `combat act`, `combat end`
- `ooc <...>`
- `recap generate`
- failure responses (`system_error`)

Each integrated response includes:

- `ui` (validated canonical envelope)
- `ui_markdown` (numbered chat rendering)
