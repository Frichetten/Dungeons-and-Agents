# Player Guide

This file defines player-facing controls and expectations for campaign sessions.

## Mode Commands

- `/play`: switch the assistant into campaign play mode.
- `/dev`: leave campaign play mode and return to engineering mode.

## Player Commands

- `/recap`
- `/sheet`
- `/items` (alias: `/inventory`)
- `/locations` (alias: `/map`)
- `/quests`
- `/rumors`
- `/time`

## DM-Only Commands

- `/refresh`
- `/savepoint`
- `/undo_last_turn`
- `/state`
- `/dashboard`
- `/npcs`
- `/relationships`
- `/factions`

## Turn Expectations

- The assistant handles all dice and rule adjudication.
- Persistent state is updated through tools, not narrative-only text.
- `/recap` should reflect momentum: recent rewards, active pressures, and next payoff hooks.
- `/refresh` remains an internal DM continuity tool (used automatically on resume/compaction recovery and available manually for DM debugging).
- Actionable narrative turns end with: `What do you do?`
