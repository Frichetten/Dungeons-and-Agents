import json
import sqlite3
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
        raise AssertionError(f"Non-JSON response: cmd={cmd} stdout={result.stdout} stderr={result.stderr}") from exc
    if expect_ok and not body.get("ok"):
        raise AssertionError(f"Unexpected failure: cmd={cmd} body={body} stderr={result.stderr}")
    if not expect_ok and body.get("ok"):
        raise AssertionError(f"Unexpected success: cmd={cmd} body={body}")
    return body


def roll_log_count(campaign_id: str) -> int:
    db_path = CAMPAIGNS_ROOT / campaign_id / "campaign.db"
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) FROM roll_log").fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


class TestDMCTLEngagementV3(unittest.TestCase):
    def setUp(self):
        self.campaign_id = f"eng_{uuid.uuid4().hex[:10]}"
        run_dmctl("campaign", "create", "--campaign", self.campaign_id, "--name", "Engagement V3")
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
                    "world_date": "2 Ches 1492 DR",
                    "world_time": "10:00",
                    "weather": "clear",
                    "region": "Greenmarch",
                    "location_id": "loc_start",
                },
            },
        )
        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "Engagement baseline")

    def tearDown(self):
        cdir = CAMPAIGNS_ROOT / self.campaign_id
        if cdir.exists():
            shutil.rmtree(cdir)

    def test_00_agenda_cadence_idempotent(self):
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        upsert = run_dmctl(
            "agenda",
            "upsert",
            "--campaign",
            self.campaign_id,
            payload={
                "name": "Bandit Escalation",
                "effect_type": "clock_tick",
                "cadence_turns": 2,
                "payload": {"name": "Bandit Escalation Clock", "amount": 1, "max_segments": 6},
            },
        )
        self.assertEqual(upsert["data"]["agenda"]["name"], "Bandit Escalation")

        pulse_1 = run_dmctl("world", "pulse", "--campaign", self.campaign_id, payload={"hours": 1})
        self.assertEqual(pulse_1["data"]["summary"]["agenda_rules_applied"], 1)

        pulse_2 = run_dmctl("world", "pulse", "--campaign", self.campaign_id, payload={"hours": 1})
        self.assertEqual(pulse_2["data"]["summary"]["agenda_rules_applied"], 0)
        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "Agenda turn one")

        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        pulse_3 = run_dmctl("world", "pulse", "--campaign", self.campaign_id, payload={"hours": 1})
        self.assertEqual(pulse_3["data"]["summary"]["agenda_rules_applied"], 0)
        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "Agenda cooldown turn")

        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        pulse_4 = run_dmctl("world", "pulse", "--campaign", self.campaign_id, payload={"hours": 1})
        self.assertEqual(pulse_4["data"]["summary"]["agenda_rules_applied"], 1)
        state = run_dmctl(
            "state",
            "get",
            "--campaign",
            self.campaign_id,
            "--include-hidden",
            payload={"full": True},
        )
        clocks = [c for c in state["data"]["clocks"] if c["name"] == "Bandit Escalation Clock"]
        self.assertEqual(len(clocks), 1)
        self.assertEqual(clocks[0]["current_segments"], 2)

    def test_01_reward_atomicity(self):
        baseline = run_dmctl(
            "state",
            "get",
            "--campaign",
            self.campaign_id,
            "--include-hidden",
            payload={"full": True},
        )
        hero_before = [pc for pc in baseline["data"]["players"] if pc["id"] == "pc_hero"][0]
        money_before = hero_before["money_cp"]

        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        failed = run_dmctl(
            "reward",
            "grant",
            "--campaign",
            self.campaign_id,
            payload={
                "grants": [
                    {"recipient_type": "pc", "recipient_id": "pc_hero", "reward": {"currency_cp": 50}},
                    {
                        "recipient_type": "party",
                        "recipient_id": "party",
                        "reward": {"faction_deltas": [{"faction_id": "fac_missing", "trust_delta": 2}]},
                    },
                ]
            },
            expect_ok=False,
        )
        self.assertEqual(failed["error"], "faction_not_found")

        state = run_dmctl(
            "state",
            "get",
            "--campaign",
            self.campaign_id,
            "--include-hidden",
            payload={"full": True},
        )
        hero_after = [pc for pc in state["data"]["players"] if pc["id"] == "pc_hero"][0]
        self.assertEqual(hero_after["money_cp"], money_before)

        history = run_dmctl("reward", "history", "--campaign", self.campaign_id, payload={"limit": 20})
        self.assertEqual(history["data"]["count"], 0)
        run_dmctl("turn", "rollback", "--campaign", self.campaign_id, payload={"reason": "reward atomicity"})

    def test_02_quest_auto_grant(self):
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        quest = run_dmctl(
            "quest",
            "add",
            "--campaign",
            self.campaign_id,
            payload={
                "id": "quest_auto",
                "title": "Clear the Watchtower",
                "description": "Drive out the raiders.",
                "auto_grant": True,
                "reward": {
                    "grants": [
                        {"recipient_type": "pc", "recipient_id": "pc_hero", "reward": {"xp": 120, "currency_cp": 35}}
                    ]
                },
            },
        )
        self.assertEqual(quest["data"]["quest"]["id"], "quest_auto")
        updated = run_dmctl(
            "quest",
            "update",
            "--campaign",
            self.campaign_id,
            payload={"quest_id": "quest_auto", "status": "completed"},
        )
        self.assertEqual(updated["data"]["quest"]["status"], "completed")
        self.assertEqual(len(updated["data"]["auto_granted_rewards"]), 1)
        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "Quest reward auto-grant")

        state = run_dmctl(
            "state",
            "get",
            "--campaign",
            self.campaign_id,
            "--include-hidden",
            payload={"full": True},
        )
        hero = [pc for pc in state["data"]["players"] if pc["id"] == "pc_hero"][0]
        self.assertEqual(hero["xp_total"], 120)
        self.assertEqual(hero["money_cp"], 35)
        history = run_dmctl("reward", "history", "--campaign", self.campaign_id)
        self.assertGreaterEqual(history["data"]["count"], 1)

    def test_03_combat_resolve_attack_and_save(self):
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        run_dmctl(
            "npc",
            "create",
            "--campaign",
            self.campaign_id,
            payload={
                "id": "npc_raider_v3",
                "name": "Road Raider V3",
                "location_id": "loc_start",
                "max_hp": 16,
                "current_hp": 16,
                "ac": 13,
                "initiative_mod": 1,
            },
        )
        start = run_dmctl(
            "combat",
            "start",
            "--campaign",
            self.campaign_id,
            payload={
                "name": "Resolve Drill",
                "location_id": "loc_start",
                "participants": [{"type": "pc", "id": "pc_hero"}, {"type": "npc", "id": "npc_raider_v3"}],
            },
        )
        encounter_id = start["data"]["encounter_id"]
        target = [c for c in start["data"]["combatants"] if c["source_type"] == "npc"][0]["id"]

        attack = run_dmctl(
            "combat",
            "resolve",
            "--campaign",
            self.campaign_id,
            payload={
                "mode": "attack",
                "encounter_id": encounter_id,
                "target_id": target,
                "attack_bonus": 30,
                "damage_formula": "1d1+2",
                "critical_threshold": 1,
                "use_action": False,
                "end_turn": False,
            },
        )
        self.assertEqual(attack["data"]["resolution"]["mode"], "attack")
        self.assertIn("damage_applied", attack["data"]["resolution"])
        self.assertGreaterEqual(len(attack["data"]["rolls"]), 1)

        save = run_dmctl(
            "combat",
            "resolve",
            "--campaign",
            self.campaign_id,
            payload={
                "mode": "save",
                "encounter_id": encounter_id,
                "target_id": target,
                "save_dc": 100,
                "save_bonus": 0,
                "on_fail_damage_formula": "1d1+4",
                "use_action": False,
                "end_turn": False,
            },
        )
        self.assertEqual(save["data"]["resolution"]["mode"], "save")
        self.assertFalse(save["data"]["resolution"]["save_success"])
        self.assertGreaterEqual(save["data"]["resolution"]["damage_applied"], 1)

    def test_04_travel_ration_shortage_soft_and_strict(self):
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        soft = run_dmctl(
            "travel",
            "resolve",
            "--campaign",
            self.campaign_id,
            payload={"to_location_id": "loc_keep", "travel_hours": 2, "consume_rations": True},
        )
        self.assertEqual(soft["data"]["ration_shortage_policy"], "soft")
        self.assertGreaterEqual(soft["data"]["ration_shortages"], 1)
        self.assertGreaterEqual(len(soft["warnings"]), 1)
        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "Soft ration shortage")

        state = run_dmctl(
            "state",
            "get",
            "--campaign",
            self.campaign_id,
            "--include-hidden",
            payload={"full": True},
        )
        hero = [pc for pc in state["data"]["players"] if pc["id"] == "pc_hero"][0]
        self.assertEqual(hero["exhaustion"], 1)

        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        strict = run_dmctl(
            "travel",
            "resolve",
            "--campaign",
            self.campaign_id,
            payload={
                "to_location_id": "loc_start",
                "travel_hours": 1,
                "consume_rations": True,
                "ration_shortage_policy": "strict",
            },
            expect_ok=False,
        )
        self.assertEqual(strict["error"], "insufficient_inventory")
        run_dmctl("turn", "rollback", "--campaign", self.campaign_id, payload={"reason": "strict shortage test"})

    def test_05_combat_resolve_failure_does_not_persist_rolls(self):
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        run_dmctl(
            "npc",
            "create",
            "--campaign",
            self.campaign_id,
            payload={
                "id": "npc_guard_v3",
                "name": "Gate Guard",
                "location_id": "loc_start",
                "max_hp": 18,
                "current_hp": 18,
                "ac": 12,
                "initiative_mod": 1,
            },
        )
        start = run_dmctl(
            "combat",
            "start",
            "--campaign",
            self.campaign_id,
            payload={
                "name": "Resolve Rejection Drill",
                "location_id": "loc_start",
                "participants": [{"type": "pc", "id": "pc_hero"}, {"type": "npc", "id": "npc_guard_v3"}],
            },
        )
        encounter_id = start["data"]["encounter_id"]
        target = [c for c in start["data"]["combatants"] if c["source_type"] == "npc"][0]["id"]

        initial_count = roll_log_count(self.campaign_id)
        first = run_dmctl(
            "combat",
            "resolve",
            "--campaign",
            self.campaign_id,
            payload={
                "mode": "attack",
                "encounter_id": encounter_id,
                "target_id": target,
                "attack_bonus": 8,
                "damage_formula": "1d1+1",
                "use_action": True,
                "end_turn": False,
            },
        )
        self.assertEqual(first["data"]["resolution"]["mode"], "attack")
        after_first = roll_log_count(self.campaign_id)
        self.assertGreater(after_first, initial_count)

        failed = run_dmctl(
            "combat",
            "resolve",
            "--campaign",
            self.campaign_id,
            payload={
                "mode": "attack",
                "encounter_id": encounter_id,
                "target_id": target,
                "attack_bonus": 8,
                "damage_formula": "1d1+1",
                "use_action": True,
                "end_turn": False,
            },
            expect_ok=False,
        )
        self.assertEqual(failed["error"], "action_already_used")
        after_failed = roll_log_count(self.campaign_id)
        self.assertEqual(after_failed, after_first)
        run_dmctl("turn", "rollback", "--campaign", self.campaign_id, payload={"reason": "combat resolve rejection roll log"})

    def test_06_time_rollover_and_ooc_contract(self):
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        run_dmctl(
            "state",
            "set",
            "--campaign",
            self.campaign_id,
            payload={"world_state": {"world_date": "30 Nightal 1492 DR", "world_time": "23:30"}},
        )
        run_dmctl("world", "pulse", "--campaign", self.campaign_id, payload={"hours": 1})
        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "Calendar rollover")

        ooc_time = run_dmctl("ooc", "time", "--campaign", self.campaign_id)
        self.assertEqual(ooc_time["data"]["time"]["world_date"], "1 Hammer 1493 DR")
        self.assertEqual(ooc_time["data"]["time"]["world_time"], "00:30")

        dashboard = run_dmctl("ooc", "dashboard", "--campaign", self.campaign_id)
        self.assertIn("recent_rewards", dashboard["data"])
        self.assertIn("active_pressures", dashboard["data"])
        self.assertIn("next_payoff_hooks", dashboard["data"])

        recap = run_dmctl("recap", "generate", "--campaign", self.campaign_id)
        self.assertIn("recent_rewards", recap["data"])
        self.assertIn("active_pressures", recap["data"])
        self.assertIn("next_payoff_hooks", recap["data"])

    def test_07_legacy_world_date_day_count_parses(self):
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        run_dmctl(
            "state",
            "set",
            "--campaign",
            self.campaign_id,
            payload={"world_state": {"world_date": "100 Hammer 1492 DR", "world_time": "08:00"}},
        )
        run_dmctl("world", "pulse", "--campaign", self.campaign_id, payload={"hours": 24})
        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "Legacy day count progression")

        ooc_time = run_dmctl("ooc", "time", "--campaign", self.campaign_id)
        self.assertEqual(ooc_time["data"]["time"]["world_date"], "11 Tarsakh 1492 DR")


if __name__ == "__main__":
    unittest.main(verbosity=2)
