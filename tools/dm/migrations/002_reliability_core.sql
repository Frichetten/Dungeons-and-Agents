PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS applied_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    applied_at TEXT NOT NULL
);

ALTER TABLE turns ADD COLUMN checkpoint_path TEXT NOT NULL DEFAULT '';
ALTER TABLE turns ADD COLUMN checkpoint_checksum TEXT NOT NULL DEFAULT '';
ALTER TABLE turns ADD COLUMN checkpoint_created_at TEXT;

ALTER TABLE events ADD COLUMN stage TEXT NOT NULL DEFAULT 'committed' CHECK(stage IN ('staged', 'committed', 'discarded'));
ALTER TABLE events ADD COLUMN flushed_to_log INTEGER NOT NULL DEFAULT 1 CHECK(flushed_to_log IN (0, 1));
ALTER TABLE events ADD COLUMN discarded_at TEXT;

ALTER TABLE combatants ADD COLUMN action_used INTEGER NOT NULL DEFAULT 0 CHECK(action_used IN (0, 1));
ALTER TABLE combatants ADD COLUMN bonus_action_used INTEGER NOT NULL DEFAULT 0 CHECK(bonus_action_used IN (0, 1));
ALTER TABLE combatants ADD COLUMN reaction_used INTEGER NOT NULL DEFAULT 0 CHECK(reaction_used IN (0, 1));
ALTER TABLE combatants ADD COLUMN movement_used_ft INTEGER NOT NULL DEFAULT 0 CHECK(movement_used_ft >= 0);

CREATE TABLE IF NOT EXISTS turn_diffs (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    turn_id INTEGER NOT NULL UNIQUE REFERENCES turns(id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,
    diff_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agenda_rules (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    effect_type TEXT NOT NULL,
    target_type TEXT NOT NULL DEFAULT '',
    target_id TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    cadence_turns INTEGER NOT NULL DEFAULT 1 CHECK(cadence_turns > 0),
    last_applied_turn INTEGER,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_facts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    owner_type TEXT NOT NULL CHECK(owner_type IN ('pc', 'npc', 'faction')),
    owner_id TEXT NOT NULL,
    fact TEXT NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'private' CHECK(visibility IN ('private', 'public', 'discovered')),
    source TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rumor_links (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    rumor_id TEXT NOT NULL REFERENCES rumors(id) ON DELETE CASCADE,
    secret_id TEXT NOT NULL REFERENCES secrets(id) ON DELETE CASCADE,
    min_spread_level INTEGER NOT NULL DEFAULT 1 CHECK(min_spread_level >= 0),
    auto_reveal INTEGER NOT NULL DEFAULT 1 CHECK(auto_reveal IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(campaign_id, rumor_id, secret_id)
);

CREATE INDEX IF NOT EXISTS idx_events_campaign_stage ON events(campaign_id, stage);
CREATE INDEX IF NOT EXISTS idx_turn_diffs_campaign_turn ON turn_diffs(campaign_id, turn_id);
CREATE INDEX IF NOT EXISTS idx_rumor_links_campaign ON rumor_links(campaign_id, rumor_id, secret_id);
CREATE INDEX IF NOT EXISTS idx_spells_active_caster ON spells_active(campaign_id, caster_type, caster_id);
CREATE INDEX IF NOT EXISTS idx_conditions_target ON conditions(campaign_id, target_type, target_id);

UPDATE events SET stage = 'committed' WHERE stage IS NULL OR stage = '';
UPDATE events SET flushed_to_log = 1 WHERE flushed_to_log IS NULL;
UPDATE campaigns SET schema_version = 2 WHERE schema_version < 2;
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '2')
ON CONFLICT(key) DO UPDATE SET value = '2';
