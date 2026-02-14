@AGENTS.md

# CLAUDE.md

Claude-specific routing for this repository.

- Default to engineering mode.
- Do not apply play-mode narrative rules unless the user explicitly asks to play or resume a campaign.
- On explicit play requests (`/play`, start/resume campaign, equivalent intent), read `.dm/PLAY_MODE.md` and follow it as the active runtime contract.
- Use `docs/PLAYER_GUIDE.md` for player command expectations and mode-switch conventions.
