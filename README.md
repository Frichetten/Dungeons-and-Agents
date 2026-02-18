# Dungeons and Agents

Persistent local D&D 5e campaign engine with SQLite, migration-driven schema upgrades, staged turn events, and deterministic state diffs.

## Core Guarantees

- SQLite is the source of truth per campaign at `.dm/campaigns/<campaign_id>/campaign.db`.
- Every mutation writes an event row; open-turn events are staged and only flushed to `events.ndjson` on successful commit.
- Turn checkpoints are created at `turn begin` and verified by checksum on `turn commit` and `turn rollback`.
- `turn commit` persists a structured state diff and updates `snapshot.json` atomically.
- `turn rollback` restores from checkpoint and discards staged events.

## Turn Lifecycle

1. `dmctl campaign load --campaign <id>`
2. `dmctl turn begin --campaign <id>`
3. Run mutation commands (`state set`, `npc update`, `combat act`, etc.)
4. `dmctl turn commit --campaign <id>` or `dmctl turn rollback --campaign <id>`
5. Use `dmctl turn diff --campaign <id>` for the latest persisted diff.

## New Command Surface

- `dmctl campaign seed`
- `dmctl campaign repair-events`
- `dmctl turn diff`
- `dmctl world pulse`
- `dmctl rest resolve`
- `dmctl travel resolve`
- `dmctl agenda <upsert|list|disable>`
- `dmctl reward <grant|history>`
- `dmctl spell cast`
- `dmctl spell end`
- `dmctl combat resolve`
- `dmctl ooc <recap|refresh|sheet|inventory|quests|rumors|npcs|relationships|factions|time|map|state|savepoint|undo_last_turn|dashboard>`
- `dmctl player <sheet|items|inventory|locations|map|rumors|quests|time>`
- `pcctl <sheet|items|inventory|locations|map|rumors|quests|time>` (player-safe wrapper)

All commands return JSON only.

## Compact Responses

- High-volume commands now default to compact payloads (`turn commit`, `turn rollback`, `ooc dashboard`, `ooc refresh` in `auto/compact` mode, `recap generate`, and `state get` without `--path`).
- Use `--full` to request the legacy verbose payload for debugging or tooling compatibility.
- Use `state get --path <key>` (or comma-separated keys) to fetch only the state slices you need.
- `/recap` is player-facing momentum recap; `/refresh` is DM continuity rehydration that rebuilds memory context from persisted state.
- Player-facing CLI lookups should use `dmctl player ...` (or `pcctl ...`) to enforce safe field projections.

## Run

```bash
./tools/dmctl campaign create --campaign demo --name "Demo Campaign"
./tools/dmctl turn begin --campaign demo
./tools/dmctl campaign seed --campaign demo --payload '{"player_characters":[{"id":"pc_hero","name":"Arin","max_hp":20,"current_hp":20}],"npcs":[{"name":"Mayor Elira"},{"name":"Sergeant Bram"},{"name":"Scholar Nyx"}]}'
./tools/dmctl world pulse --campaign demo --payload '{"hours":2,"clock_ticks":[{"name":"Bandit retaliation","amount":1}]}'
./tools/dmctl turn commit --campaign demo --summary "Session opening complete"
./tools/dmctl validate --campaign demo
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Agent Instruction Layout

- Engineering/default agent instructions: `AGENTS.md`
- Claude routing and compatibility notes: `CLAUDE.md`
- Gameplay runtime contract: `.dm/PLAY_MODE.md`
- Player-facing command reference: `docs/PLAYER_GUIDE.md`
