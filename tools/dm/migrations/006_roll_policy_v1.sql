PRAGMA foreign_keys = ON;

ALTER TABLE roll_log ADD COLUMN adjudication_id TEXT NOT NULL DEFAULT '';
ALTER TABLE roll_log ADD COLUMN policy_decision TEXT NOT NULL DEFAULT '';
ALTER TABLE roll_log ADD COLUMN policy_mode TEXT NOT NULL DEFAULT 'warn' CHECK(policy_mode IN ('warn', 'strict'));
ALTER TABLE roll_log ADD COLUMN strict_violation INTEGER NOT NULL DEFAULT 0 CHECK(strict_violation IN (0, 1));
ALTER TABLE roll_log ADD COLUMN override_reason TEXT NOT NULL DEFAULT '';
ALTER TABLE roll_log ADD COLUMN reason_codes_json TEXT NOT NULL DEFAULT '[]';

UPDATE campaigns SET schema_version = 6 WHERE schema_version < 6;
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '6')
ON CONFLICT(key) DO UPDATE SET value = '6';
