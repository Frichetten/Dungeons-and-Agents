import shutil
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DM_MIGRATIONS = ROOT / "tools" / "dm" / "migrations"
SCHEMA_SQL = ROOT / "tools" / "dm" / "schema.sql"
DMCTL = ROOT / "tools" / "dmctl"
CAMPAIGNS_ROOT = ROOT / ".dm" / "campaigns"


class TestDMCTLMigrationsV2(unittest.TestCase):
    def test_migration_files_monotonic(self):
        files = sorted(path.name for path in DM_MIGRATIONS.glob("*.sql"))
        self.assertEqual(
            files,
            [
                "001_init.sql",
                "002_reliability_core.sql",
                "003_engagement_rewards.sql",
                "004_player_views.sql",
                "005_npc_full_stat_blocks.sql",
                "006_roll_policy_v1.sql",
            ],
        )

    def test_schema_contains_v2_tables(self):
        sql = SCHEMA_SQL.read_text(encoding="utf-8")
        for token in [
            "CREATE TABLE IF NOT EXISTS applied_migrations",
            "CREATE TABLE IF NOT EXISTS turn_diffs",
            "CREATE TABLE IF NOT EXISTS agenda_rules",
            "CREATE TABLE IF NOT EXISTS knowledge_facts",
            "CREATE TABLE IF NOT EXISTS reward_events",
            "CREATE TABLE IF NOT EXISTS rumor_links",
            "stage TEXT NOT NULL DEFAULT 'committed'",
            "checkpoint_checksum",
            "action_used INTEGER NOT NULL DEFAULT 0",
            "world_day_index INTEGER NOT NULL DEFAULT 0",
            "xp_total INTEGER NOT NULL DEFAULT 0",
            "reward_json TEXT NOT NULL DEFAULT '{}'",
            "CREATE TABLE IF NOT EXISTS location_discoveries",
            "CREATE TABLE IF NOT EXISTS npcs",
            "char_class TEXT NOT NULL DEFAULT ''",
            "prepared_spells_json TEXT NOT NULL DEFAULT '[]'",
            "policy_decision TEXT NOT NULL DEFAULT ''",
            "reason_codes_json TEXT NOT NULL DEFAULT '[]'",
        ]:
            self.assertIn(token, sql)

    def test_fresh_schema_matches_expected_tables(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "schema.db"
            conn = sqlite3.connect(db_path)
            conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
            tables = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            conn.close()

        expected = {
            "applied_migrations",
            "campaigns",
            "turns",
            "events",
            "turn_diffs",
            "agenda_rules",
            "knowledge_facts",
            "reward_events",
            "rumor_links",
            "combatants",
            "location_discoveries",
        }
        self.assertTrue(expected.issubset(tables))


if __name__ == "__main__":
    unittest.main(verbosity=2)
