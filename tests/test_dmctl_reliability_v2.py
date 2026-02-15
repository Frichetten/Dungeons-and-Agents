import json
import shutil
import sqlite3
import subprocess
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DMCTL = ROOT / "tools" / "dmctl"
CAMPAIGNS_ROOT = ROOT / ".dm" / "campaigns"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "compatibility_outputs.json"


def run_dmctl(*parts, payload=None, expect_ok=True):
    cmd = [str(DMCTL), *parts]
    if payload is not None:
        cmd.extend(["--payload", json.dumps(payload, separators=(",", ":"))])

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), check=False)
    try:
        body = json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"Command did not return JSON. CMD={cmd} STDOUT={result.stdout} STDERR={result.stderr}"
        ) from exc

    if expect_ok and not body.get("ok"):
        raise AssertionError(f"Command failed unexpectedly. CMD={cmd} BODY={body} STDERR={result.stderr}")
    if not expect_ok and body.get("ok"):
        raise AssertionError(f"Command unexpectedly succeeded. CMD={cmd} BODY={body}")
    return body


class TestDMCTLReliabilityV2(unittest.TestCase):
    def setUp(self):
        self.campaign_id = f"rel_{uuid.uuid4().hex[:10]}"
        run_dmctl("campaign", "create", "--campaign", self.campaign_id, "--name", "Reliability V2")
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        run_dmctl(
            "campaign",
            "seed",
            "--campaign",
            self.campaign_id,
            payload={
                "locations": [
                    {"id": "loc_start", "name": "Larkspur", "region": "Greenmarch"},
                    {"id": "loc_keep", "name": "Old Keep", "region": "Greenmarch"},
                ],
                "player_characters": [
                    {
                        "id": "pc_hero",
                        "name": "Arin Vale",
                        "class": "Rogue",
                        "level": 3,
                        "max_hp": 24,
                        "current_hp": 24,
                        "ac": 15,
                        "location_id": "loc_start",
                        "initiative_mod": 3,
                    }
                ],
                "npcs": [
                    {"id": "npc_mayor", "name": "Mayor Elira Thorn", "location_id": "loc_start", "max_hp": 11, "current_hp": 11, "ac": 12},
                    {"id": "npc_sergeant", "name": "Sergeant Bram", "location_id": "loc_start", "max_hp": 12, "current_hp": 12, "ac": 13},
                    {"id": "npc_scholar", "name": "Scholar Nyx", "location_id": "loc_start", "max_hp": 9, "current_hp": 9, "ac": 11},
                ],
                "world_state": {
                    "world_date": "1 Ches 1492 DR",
                    "world_time": "08:00",
                    "weather": "mist",
                    "region": "Greenmarch",
                    "location_id": "loc_start",
                },
                "hooks": ["Find who stole the Ashen Crown"],
            },
        )
        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "Session zero seed")

    def tearDown(self):
        cdir = CAMPAIGNS_ROOT / self.campaign_id
        if cdir.exists():
            shutil.rmtree(cdir)

    def _campaign_db(self):
        return CAMPAIGNS_ROOT / self.campaign_id / "campaign.db"

    def _events_path(self):
        return CAMPAIGNS_ROOT / self.campaign_id / "events.ndjson"

    def _db_event_ids(self):
        conn = sqlite3.connect(self._campaign_db())
        conn.row_factory = sqlite3.Row
        ids = [
            row["id"]
            for row in conn.execute(
                "SELECT id FROM events WHERE campaign_id = ? AND stage = 'committed' ORDER BY rowid",
                (self.campaign_id,),
            )
        ]
        conn.close()
        return ids

    def _file_event_ids(self):
        ids = []
        for line in self._events_path().read_text(encoding="utf-8").splitlines():
            if line.strip():
                ids.append(json.loads(line)["id"])
        return ids

    def test_00_migrations_and_schema_health(self):
        validate = run_dmctl("validate", "--campaign", self.campaign_id)
        self.assertTrue(validate["ok"])

        conn = sqlite3.connect(self._campaign_db())
        conn.row_factory = sqlite3.Row
        schema_version = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
        applied = [r["name"] for r in conn.execute("SELECT name FROM applied_migrations ORDER BY version")]
        conn.close()

        self.assertEqual(int(schema_version["value"]), 3)
        self.assertIn("001_init.sql", applied)
        self.assertIn("002_reliability_core.sql", applied)
        self.assertIn("003_engagement_rewards.sql", applied)

    def test_01_turn_diff_required_categories(self):
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        run_dmctl(
            "state",
            "set",
            "--campaign",
            self.campaign_id,
            payload={
                "world_state": {"world_time": "09:00", "weather": "rain"},
                "public_note": "Storm clouds gather.",
            },
        )
        run_dmctl(
            "relationship",
            "adjust",
            "--campaign",
            self.campaign_id,
            payload={
                "source_type": "pc",
                "source_id": "pc_hero",
                "target_type": "npc",
                "target_id": "npc_mayor",
                "trust_delta": 1,
                "reputation_delta": 1,
            },
        )
        commit = run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "Morning updates")
        self.assertIn("diff_summary", commit["data"])
        self.assertIn("snapshot_ref", commit["data"])

        diff = run_dmctl("turn", "diff", "--campaign", self.campaign_id)
        payload = diff["data"]["diff"]
        for key in [
            "time_advanced",
            "location_change",
            "hp_resources_changed",
            "inventory_currency_changed",
            "relationship_reputation_changed",
            "quest_rumor_clock_updates",
        ]:
            self.assertIn(key, payload)

    def test_02_rollback_event_log_parity(self):
        marker_name = f"RollbackParity-{uuid.uuid4().hex[:6]}"

        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        run_dmctl(
            "item",
            "grant",
            "--campaign",
            self.campaign_id,
            payload={
                "owner_type": "pc",
                "owner_id": "pc_hero",
                "item_name": marker_name,
                "quantity": 2,
            },
        )
        run_dmctl("turn", "rollback", "--campaign", self.campaign_id, payload={"reason": "Parity check"})

        conn = sqlite3.connect(self._campaign_db())
        conn.row_factory = sqlite3.Row
        staged_count = conn.execute(
            "SELECT COUNT(*) AS c FROM events WHERE campaign_id = ? AND stage = 'staged'",
            (self.campaign_id,),
        ).fetchone()["c"]
        conn.close()

        self.assertEqual(staged_count, 0)
        self.assertEqual(self._db_event_ids(), self._file_event_ids())

        state = run_dmctl("state", "get", "--campaign", self.campaign_id, "--include-hidden", "--full")
        names = {row["item_name"] for row in state["data"]["inventory"]}
        self.assertNotIn(marker_name, names)

    def test_03_seed_requires_minimum_npcs(self):
        campaign_id = f"seed_{uuid.uuid4().hex[:8]}"
        try:
            run_dmctl("campaign", "create", "--campaign", campaign_id)
            run_dmctl("turn", "begin", "--campaign", campaign_id)
            bad = run_dmctl(
                "campaign",
                "seed",
                "--campaign",
                campaign_id,
                payload={
                    "player_characters": [{"id": "pc_x", "name": "Solo", "max_hp": 10, "current_hp": 10}],
                    "npcs": [{"name": "Only One"}],
                },
                expect_ok=False,
            )
            self.assertEqual(bad["error"], "seed_requires_three_npcs")
        finally:
            cdir = CAMPAIGNS_ROOT / campaign_id
            if cdir.exists():
                shutil.rmtree(cdir)

    def test_04_compatibility_fixture_contract(self):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        c_id = f"compat_{uuid.uuid4().hex[:8]}"
        try:
            create = run_dmctl("campaign", "create", "--campaign", c_id, "--name", "Compat")
            self.assertEqual(create["command"], fixture["campaign_create"]["command"])
            for key in fixture["campaign_create"]["data_keys"]:
                self.assertIn(key, create["data"])

            begin = run_dmctl("turn", "begin", "--campaign", c_id)
            self.assertEqual(begin["command"], fixture["turn_begin"]["command"])
            for key in fixture["turn_begin"]["data_keys"]:
                self.assertIn(key, begin["data"])

            run_dmctl(
                "campaign",
                "seed",
                "--campaign",
                c_id,
                payload={
                    "player_characters": [{"id": "pc_a", "name": "A", "max_hp": 10, "current_hp": 10}],
                    "npcs": [{"name": "N1"}, {"name": "N2"}, {"name": "N3"}],
                },
            )
            commit = run_dmctl("turn", "commit", "--campaign", c_id, "--summary", "Compat turn")
            self.assertEqual(commit["command"], fixture["turn_commit"]["command"])
            for key in fixture["turn_commit"]["data_keys"]:
                self.assertIn(key, commit["data"])

            run_dmctl("turn", "begin", "--campaign", c_id)
            commit_full = run_dmctl("turn", "commit", "--campaign", c_id, "--summary", "Compat verbose", "--full")
            self.assertIn("turn_diff", commit_full["data"])
            self.assertIn("snapshot", commit_full["data"])

            turn_diff = run_dmctl("turn", "diff", "--campaign", c_id)
            self.assertEqual(turn_diff["command"], fixture["turn_diff"]["command"])
            for key in fixture["turn_diff"]["data_keys"]:
                self.assertIn(key, turn_diff["data"])
        finally:
            cdir = CAMPAIGNS_ROOT / c_id
            if cdir.exists():
                shutil.rmtree(cdir)

    def test_05_item_grant_creates_missing_explicit_item_id(self):
        explicit_item_id = f"item_explicit_{uuid.uuid4().hex[:6]}"
        item_name = f"Trace Fiber {uuid.uuid4().hex[:6]}"

        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        granted = run_dmctl(
            "item",
            "grant",
            "--campaign",
            self.campaign_id,
            payload={
                "owner_type": "pc",
                "owner_id": "pc_hero",
                "item_id": explicit_item_id,
                "item_name": item_name,
                "stackable": False,
                "quantity": 1,
            },
        )
        self.assertEqual(granted["data"]["item"]["id"], explicit_item_id)
        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "explicit item grant")

        state = run_dmctl("state", "get", "--campaign", self.campaign_id, "--include-hidden", "--full")
        names = {row["item_name"] for row in state["data"]["inventory"]}
        self.assertIn(item_name, names)

    def test_06_quest_update_normalizes_status_and_validates_objectives(self):
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        run_dmctl(
            "quest",
            "add",
            "--campaign",
            self.campaign_id,
            payload={
                "id": "quest_status_norm",
                "title": "Status Normalization Drill",
                "description": "Exercise quest/objective status handling.",
            },
        )
        updated = run_dmctl(
            "quest",
            "update",
            "--campaign",
            self.campaign_id,
            payload={
                "quest_id": "quest_status_norm",
                "status": "complete",
                "objective_updates": [
                    {
                        "id": "obj_status_norm",
                        "description": "Interview the witness.",
                        "status": "completed",
                        "order_index": 0,
                    }
                ],
            },
        )
        self.assertEqual(updated["data"]["quest"]["status"], "completed")
        objective = [row for row in updated["data"]["objectives"] if row["id"] == "obj_status_norm"]
        self.assertEqual(len(objective), 1)
        self.assertEqual(objective[0]["status"], "complete")
        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "status normalization")

        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        bad = run_dmctl(
            "quest",
            "update",
            "--campaign",
            self.campaign_id,
            payload={
                "quest_id": "quest_status_norm",
                "objective_updates": [{"id": "obj_bad_status", "status": "nonsense"}],
            },
            expect_ok=False,
        )
        self.assertEqual(bad["error"], "invalid_objective_status")
        run_dmctl("turn", "rollback", "--campaign", self.campaign_id, payload={"reason": "invalid objective status"})

    def test_07_quest_update_rejects_objective_id_from_other_quest(self):
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        run_dmctl(
            "quest",
            "add",
            "--campaign",
            self.campaign_id,
            payload={
                "id": "quest_alpha",
                "title": "Alpha Quest",
                "objectives": [{"id": "obj_shared_id", "description": "Alpha objective", "status": "open"}],
            },
        )
        run_dmctl(
            "quest",
            "add",
            "--campaign",
            self.campaign_id,
            payload={
                "id": "quest_beta",
                "title": "Beta Quest",
            },
        )
        conflict = run_dmctl(
            "quest",
            "update",
            "--campaign",
            self.campaign_id,
            payload={
                "quest_id": "quest_beta",
                "objective_updates": [{"id": "obj_shared_id", "description": "Wrong quest objective reuse"}],
            },
            expect_ok=False,
        )
        self.assertEqual(conflict["error"], "objective_id_conflict")
        self.assertEqual(conflict["details"]["objective_id"], "obj_shared_id")
        self.assertEqual(conflict["details"]["quest_id"], "quest_beta")
        self.assertEqual(conflict["details"]["existing_quest_id"], "quest_alpha")
        run_dmctl("turn", "rollback", "--campaign", self.campaign_id, payload={"reason": "objective id conflict"})

    def test_08_chained_committed_undo_maintains_event_log_parity(self):
        for idx in range(2):
            run_dmctl("turn", "begin", "--campaign", self.campaign_id)
            run_dmctl(
                "item",
                "grant",
                "--campaign",
                self.campaign_id,
                payload={
                    "owner_type": "pc",
                    "owner_id": "pc_hero",
                    "item_name": f"undo_chain_marker_{idx}_{uuid.uuid4().hex[:6]}",
                    "quantity": 1,
                },
            )
            run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", f"undo chain commit {idx}")

        first_undo = run_dmctl("ooc", "undo_last_turn", "--campaign", self.campaign_id)
        self.assertEqual(first_undo["data"]["turn"]["status"], "rolled_back")
        self.assertEqual(first_undo["data"]["turn"]["mode"], "committed")

        second_undo = run_dmctl("ooc", "undo_last_turn", "--campaign", self.campaign_id)
        self.assertEqual(second_undo["data"]["turn"]["status"], "rolled_back")
        self.assertEqual(second_undo["data"]["turn"]["mode"], "committed")

        validate = run_dmctl("validate", "--campaign", self.campaign_id)
        self.assertTrue(validate["ok"])
        self.assertEqual(self._db_event_ids(), self._file_event_ids())

    def test_09_campaign_repair_events_dry_run_then_apply(self):
        fake_id = f"evt_fake_{uuid.uuid4().hex[:10]}"
        with self._events_path().open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "id": fake_id,
                        "campaign_id": self.campaign_id,
                        "turn_id": 9999,
                        "command": "fake",
                        "payload": {},
                        "timestamp": "2000-01-01T00:00:00+00:00",
                    },
                    separators=(",", ":"),
                )
                + "\n"
            )

        dry_run = run_dmctl("campaign", "repair-events", "--campaign", self.campaign_id, "--dry-run")
        self.assertTrue(dry_run["data"]["mismatch"])
        self.assertFalse(dry_run["data"]["repaired"])
        self.assertEqual(dry_run["data"]["before"]["db_count"] + 1, dry_run["data"]["before"]["file_count"])

        repair = run_dmctl("campaign", "repair-events", "--campaign", self.campaign_id)
        self.assertTrue(repair["data"]["mismatch"])
        self.assertTrue(repair["data"]["repaired"])
        self.assertTrue(repair["data"]["backup"])
        self.assertTrue(Path(repair["data"]["backup"]).exists())

        validate = run_dmctl("validate", "--campaign", self.campaign_id)
        self.assertTrue(validate["ok"])
        self.assertEqual(self._db_event_ids(), self._file_event_ids())


if __name__ == "__main__":
    unittest.main(verbosity=2)
