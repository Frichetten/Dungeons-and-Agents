PRAGMA foreign_keys = ON;

ALTER TABLE world_state ADD COLUMN world_day_index INTEGER NOT NULL DEFAULT 0;

ALTER TABLE player_characters ADD COLUMN xp_total INTEGER NOT NULL DEFAULT 0;
ALTER TABLE player_characters ADD COLUMN inspiration INTEGER NOT NULL DEFAULT 0 CHECK(inspiration IN (0, 1));

ALTER TABLE quests ADD COLUMN reward_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE quests ADD COLUMN auto_grant INTEGER NOT NULL DEFAULT 0 CHECK(auto_grant IN (0, 1));

CREATE TABLE IF NOT EXISTS reward_events (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,
    source_type TEXT NOT NULL DEFAULT '',
    source_id TEXT NOT NULL DEFAULT '',
    recipient_type TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    reward_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reward_events_campaign_turn ON reward_events(campaign_id, turn_id);
CREATE INDEX IF NOT EXISTS idx_reward_events_campaign_created ON reward_events(campaign_id, created_at DESC);

UPDATE campaigns SET schema_version = 3 WHERE schema_version < 3;
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '3')
ON CONFLICT(key) DO UPDATE SET value = '3';
