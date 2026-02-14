# Unified Game UI Standard v1

This document defines the strict player-facing UI contract used by runtime responses.

## Contract Goals

- Use one chat-first envelope for all player-facing output.
- Keep tactical-cinematic tone: one short flavor line, then decision-critical details.
- Keep actionable turns freeform so players can declare their own actions.
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
    {"id":"rolls","label":"Rolls","content":"..."},
    {"id":"scene","label":"Scene","content":"..."},
    {"id":"outcome","label":"Outcome","content":"..."}
  ],
  "choices": [],
  "freeform_hint":"",
  "prompt":"What do you do?"
}
```

## Template Registry

- `scene_turn`
  - Sections: `rolls`, `scene`, `outcome`
- `dialogue_turn`
  - Sections: `rolls`, `scene`, `outcome`
- `combat_turn`
  - Sections: `rolls`, `scene`, `outcome`
- `exploration_turn`
  - Sections: `rolls`, `scene`, `outcome`
- `skill_check_turn`
  - Sections: `rolls`, `scene`, `outcome`
- `ooc_panel`
  - Sections: `overview`, `resources`, `objectives`, `world`
  - Non-actionable: no choices, no prompt
- `system_error`
  - Sections: `error`, `rollback`, `recovery`

## Input Grammar

Input resolution rules:

1. Freeform action text from the player.
2. Runtime interpretation of that action against current scene state.

Rendering rules:

- Actionable templates always include:
  - `choices`: empty list
  - `freeform_hint`: empty string
  - `prompt`: `What do you do?`
- Player-facing markdown should not print envelope metadata lines (`ui_contract_version`, `template_id`).

## Validation Rules

The validator rejects envelopes when:

- Required keys are missing or out of canonical order.
- `template_id` is unknown.
- Required sections are missing, mislabeled, or out of order.
- Actionable templates include any preset choices.
- Actionable templates include a non-empty `freeform_hint`.
- Actionable prompt is not exactly `What do you do?`.

## Runtime Integration

Current runtime integration points in `tools/dmctl`:

- `combat start`, `combat act`, `combat end`
- `ooc <...>`
- `recap generate`
- failure responses (`system_error`)

Each integrated response includes:

- `ui` (validated canonical envelope)
- `ui_markdown` (chat rendering)
