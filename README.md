# Dungeons and Agents

Dungeons and Agents is a local-first D&D 5e campaign engine for AI assistants. It provides a durable state backend (`tools/dmctl`) so campaigns survive restarts, compaction, and long pauses between sessions. You can use Claude Code or Codex to act as a virtual dungeon master for you to play along with.

## Why this exists

Most AI campaign demos lose continuity once the chat window resets. This project stores world state on disk and forces every world mutation through a CLI command.

Each campaign gets:
- a SQLite database (`campaign.db`)
- an append-only event log (`events.ndjson`)
- a JSON snapshot (`snapshot.json`)
- a markdown transcript (`transcript.md`)

## Requirements

- Python 3.9+
- macOS or Linux shell

## Using this with Codex

Codex reads `AGENTS.md` in this repo.

- default is engineering mode
- enter play mode with `/play` or an explicit "start/resume campaign" request
- leave play mode with `/dev`
- play-mode runtime rules live in `.dm/PLAY_MODE.md`

## Using this with Claude

Claude reads `CLAUDE.md`, which routes to the same play contract. It is worth noting that Opus 4.6 does a significantly better job when it comes to narrative content compared to any Codex model. For that reason, along with it's much larger context window that Opus 4.6 is recommended.

## Command groups

Run `./tools/dmctl --help` for the full surface. Main groups:

- `agenda`
- `campaign`
- `clock`
- `combat`
- `dice`
- `faction`
- `item`
- `npc`
- `ooc`
- `quest`
- `recap`
- `relationship`
- `rest`
- `reward`
- `rumor`
- `secret`
- `spell`
- `state`
- `travel`
- `turn`
- `validate`
- `world`

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Optional long soak test (500 turns):

```bash
DMCTL_LONG_SOAK=1 python3 -m unittest tests/test_dmctl_soak_v2.py -v
```

## Repository map

- `tools/dmctl`: executable CLI entrypoint
- `tools/dm/schema.sql`: baseline schema
- `tools/dm/migrations/`: schema migrations
- `tests/`: reliability, migration, UI contract, and engagement tests
- `AGENTS.md`: Codex routing rules
- `CLAUDE.md`: Claude routing rules
- `.dm/PLAY_MODE.md`: gameplay runtime contract
- `docs/PLAYER_GUIDE.md`: player-facing command reference
