import json
import random
import sqlite3
import shutil
import subprocess
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DMCTL = ROOT / "tools" / "dmctl"
CAMPAIGNS_ROOT = ROOT / ".dm" / "campaigns"


def run_dmctl(*parts, payload=None, expect_ok=True):
    cmd = [str(DMCTL), *parts]
    if payload is not None:
        cmd.extend(["--payload", json.dumps(payload, separators=(",", ":"))])
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), check=False)
    body = json.loads(result.stdout.strip())
    if expect_ok and not body.get("ok"):
        raise AssertionError(f"Unexpected failure: {cmd} -> {body}")
    if not expect_ok and body.get("ok"):
        raise AssertionError(f"Unexpected success: {cmd} -> {body}")
    return body


class TestDMCTLValidationV2(unittest.TestCase):
    def setUp(self):
        self.campaign_id = f"val_{uuid.uuid4().hex[:10]}"
        run_dmctl("campaign", "create", "--campaign", self.campaign_id)
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)

    def tearDown(self):
        cdir = CAMPAIGNS_ROOT / self.campaign_id
        if cdir.exists():
            shutil.rmtree(cdir)

    def test_dice_formula_fuzz(self):
        rng = random.Random(1337)
        for _ in range(80):
            pools = []
            pool_count = rng.randint(1, 3)
            for _ in range(pool_count):
                n = rng.randint(1, 4)
                sides = rng.choice([4, 6, 8, 10, 12, 20])
                pools.append(f"{n}d{sides}")
            modifier = rng.randint(-5, 5)
            formula = "+".join(pools)
            if modifier < 0:
                formula += str(modifier)
            elif modifier > 0:
                formula += f"+{modifier}"

            body = run_dmctl("dice", "roll", "--campaign", self.campaign_id, "--formula", formula)
            self.assertTrue(body["ok"])
            self.assertIn("total", body["data"])
            self.assertIn("raw_dice", body["data"])

    def test_invalid_formula_and_payload_errors(self):
        bad_formula = run_dmctl(
            "dice",
            "roll",
            "--campaign",
            self.campaign_id,
            "--formula",
            "2dd20",
            expect_ok=False,
        )
        self.assertEqual(bad_formula["error"], "invalid_dice_formula")
        self.assertIn("message", bad_formula["details"])

        bad_payload = run_dmctl(
            "state",
            "set",
            "--campaign",
            self.campaign_id,
            payload={"world_state": "not-an-object"},
            expect_ok=False,
        )
        self.assertEqual(bad_payload["error"], "invalid_world_state_payload")
        self.assertIn("message", bad_payload["details"])

    def test_validate_reports_event_log_parity_details_on_mismatch(self):
        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "validation parity baseline")
        events_path = CAMPAIGNS_ROOT / self.campaign_id / "events.ndjson"
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "id": f"evt_extra_{uuid.uuid4().hex[:8]}",
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
            handle.write("123\n")

        validate = run_dmctl("validate", "--campaign", self.campaign_id, expect_ok=False)
        self.assertEqual(validate["error"], "validation_failed")
        result = validate["details"]["results"][0]
        self.assertIn("event_log_parity", result)
        parity = result["event_log_parity"]
        for key in [
            "db_count",
            "file_count",
            "first_mismatch_index",
            "only_in_db_sample",
            "only_in_file_sample",
        ]:
            self.assertIn(key, parity)
        self.assertGreater(parity["file_count"], parity["db_count"])
        self.assertIn("parse_error", parity)

    def test_runtime_rejects_missing_relationship_and_inventory_owners(self):
        bad_relationship = run_dmctl(
            "relationship",
            "adjust",
            "--campaign",
            self.campaign_id,
            payload={
                "source_type": "pc",
                "source_id": "pc_missing",
                "target_type": "npc",
                "target_id": "npc_missing",
                "trust_delta": 1,
            },
            expect_ok=False,
        )
        self.assertEqual(bad_relationship["error"], "relationship_endpoint_not_found")

        bad_inventory = run_dmctl(
            "item",
            "grant",
            "--campaign",
            self.campaign_id,
            payload={
                "owner_type": "pc",
                "owner_id": "pc_missing",
                "item_name": "Validation Arrow",
                "quantity": 1,
            },
            expect_ok=False,
        )
        self.assertEqual(bad_inventory["error"], "inventory_owner_not_found")

        bad_party_owner = run_dmctl(
            "item",
            "grant",
            "--campaign",
            self.campaign_id,
            payload={
                "owner_type": "party",
                "owner_id": "adventurers",
                "item_name": "Validation Rope",
                "quantity": 1,
            },
            expect_ok=False,
        )
        self.assertEqual(bad_party_owner["error"], "invalid_party_owner_id")

        bad_reward = run_dmctl(
            "reward",
            "grant",
            "--campaign",
            self.campaign_id,
            payload={
                "recipient_type": "npc",
                "recipient_id": "npc_missing",
                "reward": {"hooks_add": ["probe"]},
            },
            expect_ok=False,
        )
        self.assertEqual(bad_reward["error"], "reward_recipient_not_found")

    def test_validate_detects_orphan_relationship_inventory_and_reward_references(self):
        db_path = CAMPAIGNS_ROOT / self.campaign_id / "campaign.db"
        conn = sqlite3.connect(db_path)
        ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        item_id = f"item_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """
            INSERT INTO items (
                id, campaign_id, name, description, stackable, consumable, max_charges, charges, created_at, updated_at
            ) VALUES (?, ?, ?, '', 1, 0, 0, 0, ?, ?)
            """,
            (item_id, self.campaign_id, "Orphan Probe Item", ts, ts),
        )
        conn.execute(
            """
            INSERT INTO inventories (campaign_id, owner_type, owner_id, item_id, quantity, updated_at)
            VALUES (?, 'pc', 'pc_missing', ?, 1, ?)
            """,
            (self.campaign_id, item_id, ts),
        )
        conn.execute(
            """
            INSERT INTO relationships (
                id, campaign_id, source_type, source_id, target_type, target_id, trust, fear, debt, reputation, updated_at
            ) VALUES (?, ?, 'pc', 'pc_missing', 'npc', 'npc_missing', 0, 0, 0, 0, ?)
            """,
            (f"rel_{uuid.uuid4().hex[:8]}", self.campaign_id, ts),
        )
        conn.execute(
            """
            INSERT INTO reward_events (
                id, campaign_id, turn_id, source_type, source_id, recipient_type, recipient_id, reward_json, created_at
            ) VALUES (?, ?, NULL, 'manual', '', 'npc', 'npc_missing', '{}', ?)
            """,
            (f"reward_{uuid.uuid4().hex[:8]}", self.campaign_id, ts),
        )
        conn.commit()
        conn.close()

        validate = run_dmctl("validate", "--campaign", self.campaign_id, expect_ok=False)
        self.assertEqual(validate["error"], "validation_failed")
        result = validate["details"]["results"][0]
        errors = " ".join(result["errors"])
        self.assertIn("orphan relationship endpoints found", errors)
        self.assertIn("invalid inventory owners found", errors)
        self.assertIn("invalid reward recipients found", errors)

    def test_validate_detects_orphan_active_spell_casters(self):
        db_path = CAMPAIGNS_ROOT / self.campaign_id / "campaign.db"
        conn = sqlite3.connect(db_path)
        ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        conn.execute(
            """
            INSERT INTO spells_active (
                id, campaign_id, caster_type, caster_id, spell_name, target_type, target_id,
                remaining_rounds, requires_concentration, created_at, updated_at
            ) VALUES (?, ?, 'pc', 'pc_missing', 'Mage Armor', '', '', 8, 0, ?, ?)
            """,
            (f"spell_{uuid.uuid4().hex[:8]}", self.campaign_id, ts, ts),
        )
        conn.commit()
        conn.close()

        validate = run_dmctl("validate", "--campaign", self.campaign_id, expect_ok=False)
        self.assertEqual(validate["error"], "validation_failed")
        result = validate["details"]["results"][0]
        errors = " ".join(result["errors"])
        self.assertIn("invalid active spell casters found", errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
