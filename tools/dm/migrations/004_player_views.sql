PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS location_discoveries (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    pc_id TEXT NOT NULL REFERENCES player_characters(id) ON DELETE CASCADE,
    location_id TEXT NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    discovered_at TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    UNIQUE(campaign_id, pc_id, location_id)
);

CREATE INDEX IF NOT EXISTS idx_location_discoveries_pc_time ON location_discoveries(campaign_id, pc_id, discovered_at DESC);

INSERT OR IGNORE INTO location_discoveries (id, campaign_id, pc_id, location_id, discovered_at, source)
SELECT
    lower(hex(randomblob(16))) AS id,
    pc.campaign_id,
    pc.id,
    pc.location_id,
    COALESCE(pc.updated_at, datetime('now')),
    'migration_backfill_pc_location'
FROM player_characters pc
WHERE pc.location_id IS NOT NULL;

INSERT OR IGNORE INTO location_discoveries (id, campaign_id, pc_id, location_id, discovered_at, source)
SELECT
    lower(hex(randomblob(16))) AS id,
    ws.campaign_id,
    pc.id,
    ws.location_id,
    COALESCE(ws.updated_at, datetime('now')),
    'migration_backfill_world_location'
FROM world_state ws
JOIN player_characters pc ON pc.campaign_id = ws.campaign_id AND pc.is_active = 1
WHERE ws.location_id IS NOT NULL;

UPDATE campaigns SET schema_version = 4 WHERE schema_version < 4;
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '4')
ON CONFLICT(key) DO UPDATE SET value = '4';
