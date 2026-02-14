import json
import shutil
import subprocess
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DMCTL = ROOT / "tools" / "dmctl"
CAMPAIGNS_ROOT = ROOT / ".dm" / "campaigns"


def run_dmctl(*parts, payload=None, expect_ok=True):
    cmd = [str(DMCTL), *parts]
    if payload is not None:
        cmd.extend(["--payload", json.dumps(payload, separators=(",", ":"))])

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), check=False)

    try:
        body = json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"Command did not return JSON.\nCMD: {cmd}\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        ) from exc

    if expect_ok and not body.get("ok"):
        raise AssertionError(
            f"Command failed unexpectedly.\nCMD: {cmd}\nBODY: {body}\nSTDERR: {result.stderr}"
        )
    if not expect_ok and body.get("ok"):
        raise AssertionError(f"Command unexpectedly succeeded. CMD: {cmd}\nBODY: {body}")

    return body


class TestDMCTLQualityGates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.campaign_id = f"qa_{uuid.uuid4().hex[:10]}"

    @classmethod
    def tearDownClass(cls):
        cdir = CAMPAIGNS_ROOT / cls.campaign_id
        if cdir.exists():
            shutil.rmtree(cdir)

    def test_00_create_campaign_and_session_zero_seed(self):
        create = run_dmctl("campaign", "create", "--campaign", self.campaign_id, "--name", "QA Campaign")
        self.assertTrue(create["ok"])

        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        run_dmctl(
            "state",
            "set",
            "--campaign",
            self.campaign_id,
            payload={
                "locations": [
                    {"id": "loc_town", "name": "Oakcross", "region": "Greenmarch"},
                    {"id": "loc_road", "name": "Raven Road", "region": "Greenmarch"},
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
                        "location_id": "loc_town",
                        "initiative_mod": 3,
                        "spell_slots": {"1": 2},
                    }
                ],
                "world_state": {
                    "world_date": "1 Ches 1492 DR",
                    "world_time": "08:00",
                    "weather": "mist",
                    "region": "Greenmarch",
                    "location_id": "loc_town",
                    "active_arc": "Ashen Crown",
                },
                "public_note": "Session zero complete.",
                "hidden_note": "Mayor is secretly tied to the Ashen Crown.",
            },
        )

        # At least 3 named NPCs for initial world seed.
        for name in ["Mayor Elira Thorn", "Sergeant Bram", "Scholar Nyx"]:
            run_dmctl(
                "npc",
                "create",
                "--campaign",
                self.campaign_id,
                payload={
                    "name": name,
                    "location_id": "loc_town",
                    "max_hp": 11,
                    "current_hp": 11,
                    "ac": 12,
                    "trust": 0,
                    "fear": 0,
                    "debt": 0,
                    "reputation": 0,
                },
            )

        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "Session zero seeded.")

        loaded = run_dmctl("campaign", "load", "--campaign", self.campaign_id)
        self.assertEqual(loaded["data"]["counts"]["pc_count"], 1)
        self.assertGreaterEqual(loaded["data"]["counts"]["npc_count"], 3)

    def test_01_ten_turn_simulation(self):
        for idx in range(10):
            run_dmctl("turn", "begin", "--campaign", self.campaign_id)

            run_dmctl(
                "dice",
                "roll",
                "--campaign",
                self.campaign_id,
                "--formula",
                "1d20+2",
                "--context",
                f"simulation_turn_{idx+1}",
            )

            run_dmctl(
                "state",
                "set",
                "--campaign",
                self.campaign_id,
                payload={
                    "world_state": {
                        "world_time": f"{8 + (idx % 10):02d}:00",
                        "weather": "rain" if idx % 2 else "mist",
                    },
                    "public_note": f"Simulation turn {idx+1}",
                },
            )

            if idx == 0:
                run_dmctl(
                    "quest",
                    "add",
                    "--campaign",
                    self.campaign_id,
                    payload={
                        "id": "quest_main_ashen",
                        "title": "Recover the Ashen Crown",
                        "description": "Find the stolen relic before the solstice.",
                        "is_main_arc": True,
                        "objectives": [
                            {"id": "obj_clue_1", "description": "Question the town guard."},
                            {"id": "obj_clue_2", "description": "Search the old granary."},
                        ],
                    },
                )

            if idx % 3 == 0:
                run_dmctl(
                    "clock",
                    "tick",
                    "--campaign",
                    self.campaign_id,
                    payload={"name": "Bandit retaliation", "max_segments": 6, "amount": 1},
                )

            if idx == 1:
                run_dmctl(
                    "item",
                    "grant",
                    "--campaign",
                    self.campaign_id,
                    payload={
                        "owner_type": "pc",
                        "owner_id": "pc_hero",
                        "item_name": "Potion of Healing",
                        "consumable": True,
                        "quantity": 2,
                    },
                )

            if idx == 2:
                run_dmctl(
                    "item",
                    "consume",
                    "--campaign",
                    self.campaign_id,
                    payload={
                        "owner_type": "pc",
                        "owner_id": "pc_hero",
                        "item_name": "Potion of Healing",
                        "quantity": 1,
                    },
                )

            run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", f"Sim turn {idx+1}")

        loaded = run_dmctl("campaign", "load", "--campaign", self.campaign_id)
        self.assertGreaterEqual(loaded["data"]["latest_turn"]["turn_number"], 11)

    def test_02_process_restart_persistence(self):
        # Each call is a fresh process; this verifies state survives process restart.
        first = run_dmctl("campaign", "load", "--campaign", self.campaign_id)
        second = run_dmctl("state", "get", "--campaign", self.campaign_id)
        self.assertEqual(first["data"]["campaign"]["id"], self.campaign_id)
        self.assertEqual(second["data"]["campaign"]["id"], self.campaign_id)

    def test_03_combat_flow(self):
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)

        enemy = run_dmctl(
            "npc",
            "create",
            "--campaign",
            self.campaign_id,
            payload={
                "id": "npc_raider",
                "name": "Road Raider",
                "location_id": "loc_road",
                "max_hp": 16,
                "current_hp": 16,
                "ac": 13,
                "initiative_mod": 1,
            },
        )
        self.assertEqual(enemy["data"]["npc"]["id"], "npc_raider")

        started = run_dmctl(
            "combat",
            "start",
            "--campaign",
            self.campaign_id,
            payload={
                "name": "Road Ambush",
                "location_id": "loc_road",
                "participants": [
                    {"type": "pc", "id": "pc_hero"},
                    {"type": "npc", "id": "npc_raider"},
                ],
            },
        )

        encounter_id = started["data"]["encounter_id"]
        combatants = started["data"]["combatants"]
        raider_combatant = [c for c in combatants if c["source_type"] == "npc" and c["source_id"] == "npc_raider"][0]

        act = run_dmctl(
            "combat",
            "act",
            "--campaign",
            self.campaign_id,
            payload={
                "encounter_id": encounter_id,
                "action": "Shortsword strike",
                "target_id": raider_combatant["id"],
                "damage": 6,
                "end_turn": True,
            },
        )
        self.assertTrue(act["ok"])

        ended = run_dmctl(
            "combat",
            "end",
            "--campaign",
            self.campaign_id,
            payload={"encounter_id": encounter_id, "notes": "Raider routed."},
        )
        self.assertEqual(ended["data"]["encounter"]["status"], "ended")

        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "Combat resolved.")

        state = run_dmctl("state", "get", "--campaign", self.campaign_id, "--include-hidden")
        raider_rows = [n for n in state["data"]["npcs"] if n["id"] == "npc_raider"]
        self.assertEqual(len(raider_rows), 1)
        self.assertLessEqual(raider_rows[0]["current_hp"], 10)

    def test_04_rumor_secret_reveal_chain(self):
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)

        rumor = run_dmctl(
            "rumor",
            "add",
            "--campaign",
            self.campaign_id,
            payload={
                "id": "rumor_ashen_vault",
                "text": "There is a vault under Oakcross chapel.",
                "source": "Drunk mason",
                "truth_status": "true",
                "spread_level": 1,
            },
        )
        self.assertEqual(rumor["data"]["rumor"]["id"], "rumor_ashen_vault")

        secret = run_dmctl(
            "secret",
            "add",
            "--campaign",
            self.campaign_id,
            payload={
                "id": "secret_chapel_key",
                "text": "The chapel vault key is hidden in the mayor's cane.",
                "discovery_condition": "Inspect the cane after social victory.",
                "associated_rumor_id": "rumor_ashen_vault",
            },
        )
        self.assertEqual(secret["data"]["secret"]["id"], "secret_chapel_key")

        run_dmctl(
            "rumor",
            "reveal",
            "--campaign",
            self.campaign_id,
            payload={"rumor_id": "rumor_ashen_vault"},
        )
        run_dmctl(
            "secret",
            "reveal",
            "--campaign",
            self.campaign_id,
            payload={"secret_id": "secret_chapel_key"},
        )

        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "Rumor and secret chain resolved.")

        state = run_dmctl("state", "get", "--campaign", self.campaign_id)
        rumor_ids = {r["id"] for r in state["data"]["rumors"]}
        secret_ids = {s["id"] for s in state["data"]["secrets"]}
        self.assertIn("rumor_ashen_vault", rumor_ids)
        self.assertIn("secret_chapel_key", secret_ids)

    def test_05_rollback(self):
        marker_name = f"RollbackTestItem-{uuid.uuid4().hex[:6]}"

        baseline = run_dmctl("state", "get", "--campaign", self.campaign_id, "--include-hidden")
        before_count = len([i for i in baseline["data"]["inventory"] if i["item_name"] == marker_name])

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
                "quantity": 3,
            },
        )
        run_dmctl(
            "turn",
            "rollback",
            "--campaign",
            self.campaign_id,
            payload={"reason": "Rollback test"},
        )

        after = run_dmctl("state", "get", "--campaign", self.campaign_id, "--include-hidden")
        after_count = len([i for i in after["data"]["inventory"] if i["item_name"] == marker_name])
        self.assertEqual(before_count, after_count)

    def test_06_validate(self):
        validate = run_dmctl("validate", "--campaign", self.campaign_id)
        self.assertTrue(validate["ok"])
        self.assertEqual(validate["data"]["validated_campaigns"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
