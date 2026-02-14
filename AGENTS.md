# AGENTS.md

Repository instruction router for coding agents.

Instruction precedence:
1. System/developer instructions
2. This `AGENTS.md`
3. User requests

## Default Mode: Engineering

- Treat requests as software development tasks unless the user explicitly asks to run the campaign.
- Build, debug, test, refactor, and document project tooling.
- Do not auto-enter DM narrative mode during normal engineering work.

## Play Mode Trigger

Switch to play mode only on an explicit request, such as:
- `/play`
- "start the campaign"
- "resume campaign"
- another clearly equivalent request to run the game loop

When play mode is triggered:
1. Read `.dm/PLAY_MODE.md` fully before responding.
2. Follow `.dm/PLAY_MODE.md` as the active gameplay contract.
3. Use persisted state only and apply all mutations through project tools.
4. Stay in play mode until the user explicitly switches back (for example `/dev` or a clear coding request).

## Supporting Documents

- Gameplay runtime spec: `.dm/PLAY_MODE.md`
- Player command reference: `docs/PLAYER_GUIDE.md`

Keep this root file focused on engineering and mode routing. Keep gameplay-specific rules in `.dm/PLAY_MODE.md`.
