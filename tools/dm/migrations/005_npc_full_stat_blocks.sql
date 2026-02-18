PRAGMA foreign_keys = ON;

ALTER TABLE npcs ADD COLUMN char_class TEXT NOT NULL DEFAULT '';
ALTER TABLE npcs ADD COLUMN level INTEGER NOT NULL DEFAULT 1 CHECK(level >= 1);
ALTER TABLE npcs ADD COLUMN exhaustion INTEGER NOT NULL DEFAULT 0 CHECK(exhaustion >= 0 AND exhaustion <= 6);
ALTER TABLE npcs ADD COLUMN hit_dice_total INTEGER NOT NULL DEFAULT 1 CHECK(hit_dice_total >= 0);
ALTER TABLE npcs ADD COLUMN hit_dice_used INTEGER NOT NULL DEFAULT 0 CHECK(hit_dice_used >= 0 AND hit_dice_used <= hit_dice_total);
ALTER TABLE npcs ADD COLUMN death_saves_success INTEGER NOT NULL DEFAULT 0 CHECK(death_saves_success >= 0 AND death_saves_success <= 3);
ALTER TABLE npcs ADD COLUMN death_saves_fail INTEGER NOT NULL DEFAULT 0 CHECK(death_saves_fail >= 0 AND death_saves_fail <= 3);
ALTER TABLE npcs ADD COLUMN spell_slots_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE npcs ADD COLUMN prepared_spells_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE npcs ADD COLUMN concentration_spell TEXT NOT NULL DEFAULT '';
ALTER TABLE npcs ADD COLUMN consumables_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE npcs ADD COLUMN xp_total INTEGER NOT NULL DEFAULT 0 CHECK(xp_total >= 0);
ALTER TABLE npcs ADD COLUMN inspiration INTEGER NOT NULL DEFAULT 0 CHECK(inspiration IN (0, 1));

UPDATE npcs SET level = 1 WHERE level < 1;
UPDATE npcs SET exhaustion = 0 WHERE exhaustion < 0 OR exhaustion > 6;
UPDATE npcs SET hit_dice_total = 1 WHERE hit_dice_total < 0;
UPDATE npcs SET hit_dice_used = 0 WHERE hit_dice_used < 0 OR hit_dice_used > hit_dice_total;
UPDATE npcs SET death_saves_success = 0 WHERE death_saves_success < 0 OR death_saves_success > 3;
UPDATE npcs SET death_saves_fail = 0 WHERE death_saves_fail < 0 OR death_saves_fail > 3;
UPDATE npcs SET xp_total = 0 WHERE xp_total < 0;
UPDATE npcs SET inspiration = 0 WHERE inspiration NOT IN (0, 1);

UPDATE campaigns SET schema_version = 5 WHERE schema_version < 5;
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '5')
ON CONFLICT(key) DO UPDATE SET value = '5';
