# Player Guide

This file defines player-facing controls and expectations for campaign sessions.

## Mode Commands

- `/play`: switch the assistant into campaign play mode.
- `/dev`: leave campaign play mode and return to engineering mode.

## OOC Commands

- `/recap`
- `/refresh`
- `/sheet`
- `/inventory`
- `/quests`
- `/rumors`
- `/npcs`
- `/relationships`
- `/factions`
- `/time`
- `/map`
- `/state`
- `/dashboard`
- `/savepoint`
- `/undo_last_turn` (only when rollback is valid and no branch was created)

## Turn Expectations

- The assistant handles all dice and rule adjudication.
- Persistent state is updated through tools, not narrative-only text.
- `/recap` and `/dashboard` should reflect momentum: recent rewards, active pressures, and next payoff hooks.
- `/refresh` rehydrates DM continuity context from persisted state (used automatically on resume/compaction recovery and available manually for debugging).
- Actionable narrative turns end with: `What do you do?`
