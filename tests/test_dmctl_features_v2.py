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


class TestDMCTLFeaturesV2(unittest.TestCase):
    def setUp(self):
        self.campaign_id = f"feat_{uuid.uuid4().hex[:10]}"
        run_dmctl("campaign", "create", "--campaign", self.campaign_id, "--name", "Features V2")
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
        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "Feature baseline")

    def tearDown(self):
        cdir = CAMPAIGNS_ROOT / self.campaign_id
        if cdir.exists():
            shutil.rmtree(cdir)

    def test_00_dice_expression_and_flags(self):
        expr = run_dmctl(
            "dice",
            "roll",
            "--campaign",
            self.campaign_id,
            "--formula",
            "2d6+1d4+3",
            "--context",
            "feature_expression",
        )
        self.assertEqual(expr["data"]["modifier"], 3)
        self.assertGreaterEqual(len(expr["data"]["raw_dice"]), 3)

        kd = run_dmctl(
            "dice",
            "roll",
            "--campaign",
            self.campaign_id,
            "--formula",
            "4d6",
            "--keep-highest",
            "3",
            "--drop-lowest",
            "1",
            "--context",
            "feature_keep_drop",
        )
        self.assertEqual(len(kd["data"]["selected_dice"]), 3)

        bad = run_dmctl(
            "dice",
            "roll",
            "--campaign",
            self.campaign_id,
            "--formula",
            "2d6+1d4",
            "--keep-highest",
            "1",
            expect_ok=False,
        )
        self.assertEqual(bad["error"], "invalid_roll_flags")

    def test_01_world_pulse_rumor_secret_link(self):
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)

        run_dmctl(
            "rumor",
            "add",
            "--campaign",
            self.campaign_id,
            payload={
                "id": "rumor_linked",
                "text": "A hidden chapel vault exists.",
                "source": "Stablehand",
                "truth_status": "true",
                "spread_level": 1,
                "decay": 0,
            },
        )
        run_dmctl(
            "secret",
            "add",
            "--campaign",
            self.campaign_id,
            payload={
                "id": "secret_linked",
                "text": "The vault key rests in the mayor's cane.",
                "discovery_condition": "Rumor matures",
                "associated_rumor_id": "rumor_linked",
            },
        )
        run_dmctl(
            "rumor",
            "reveal",
            "--campaign",
            self.campaign_id,
            payload={"rumor_id": "rumor_linked"},
        )

        conn = sqlite3.connect(CAMPAIGNS_ROOT / self.campaign_id / "campaign.db")
        conn.execute(
            """
            INSERT INTO rumor_links (id, campaign_id, rumor_id, secret_id, min_spread_level, auto_reveal, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, 1, datetime('now'), datetime('now'))
            """,
            (f"link_{uuid.uuid4().hex[:8]}", self.campaign_id, "rumor_linked", "secret_linked"),
        )
        conn.commit()
        conn.close()

        pulse = run_dmctl(
            "world",
            "pulse",
            "--campaign",
            self.campaign_id,
            payload={"hours": 1, "rumor_spread_shift": 1, "rumor_decay_step": 0, "add_hooks": ["Check the chapel crypt"]},
        )
        self.assertGreaterEqual(pulse["data"]["summary"]["secret_reveals"], 1)

        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "Pulse and reveal")
        state = run_dmctl("state", "get", "--campaign", self.campaign_id, "--include-hidden", "--full")
        secret_rows = [s for s in state["data"]["secrets"] if s["id"] == "secret_linked"]
        self.assertEqual(secret_rows[0]["reveal_status"], "revealed")

    def test_02_rest_travel_spell_and_ooc(self):
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)

        run_dmctl(
            "state",
            "set",
            "--campaign",
            self.campaign_id,
            payload={
                "player_characters": [
                    {
                        "id": "pc_hero",
                        "name": "Arin Vale",
                        "max_hp": 24,
                        "current_hp": 6,
                        "ac": 15,
                        "location_id": "loc_start",
                    }
                ]
            },
        )

        rest = run_dmctl(
            "rest",
            "resolve",
            "--campaign",
            self.campaign_id,
            payload={"rest_type": "long"},
        )
        self.assertEqual(rest["data"]["rest_type"], "long")
        self.assertEqual(rest["data"]["updated_pcs"][0]["current_hp"], 24)

        travel = run_dmctl(
            "travel",
            "resolve",
            "--campaign",
            self.campaign_id,
            payload={"to_location_id": "loc_keep", "travel_hours": 2},
        )
        self.assertEqual(travel["data"]["destination_id"], "loc_keep")

        cast = run_dmctl(
            "spell",
            "cast",
            "--campaign",
            self.campaign_id,
            payload={
                "caster_type": "pc",
                "caster_id": "pc_hero",
                "spell_name": "Invisibility",
                "remaining_rounds": 10,
                "requires_concentration": True,
            },
        )
        self.assertEqual(cast["data"]["spell"]["spell_name"], "Invisibility")

        run_dmctl(
            "spell",
            "end",
            "--campaign",
            self.campaign_id,
            payload={"spell_id": cast["data"]["spell"]["id"]},
        )

        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "Rest travel spell")

        sheet = run_dmctl("ooc", "sheet", "--campaign", self.campaign_id, payload={"pc_id": "pc_hero"})
        self.assertEqual(sheet["data"]["pc"]["id"], "pc_hero")

        ooc_time = run_dmctl("ooc", "time", "--campaign", self.campaign_id)
        self.assertIn("world_time", ooc_time["data"]["time"])

        ooc_map = run_dmctl("ooc", "map", "--campaign", self.campaign_id)
        self.assertEqual(ooc_map["data"]["current_location"]["location_id"], "loc_keep")

        ooc_state = run_dmctl("ooc", "state", "--campaign", self.campaign_id)
        self.assertEqual(ooc_state["data"]["profile"], "player")
        self.assertNotIn("recent_hidden_notes", ooc_state["data"])

        state_paths = run_dmctl("state", "get", "--campaign", self.campaign_id, "--path", "world_state,players")
        self.assertEqual(state_paths["data"]["paths"], ["world_state", "players"])
        self.assertIn("world_state", state_paths["data"]["values"])
        self.assertIn("players", state_paths["data"]["values"])

        dashboard = run_dmctl("ooc", "dashboard", "--campaign", self.campaign_id)
        if dashboard["data"]["latest_turn_diff"]:
            self.assertIn("diff_summary", dashboard["data"]["latest_turn_diff"])
            self.assertNotIn("diff", dashboard["data"]["latest_turn_diff"])

        dashboard_full = run_dmctl("ooc", "dashboard", "--campaign", self.campaign_id, "--full")
        if dashboard_full["data"]["latest_turn_diff"]:
            self.assertIn("diff", dashboard_full["data"]["latest_turn_diff"])

        recap = run_dmctl("ooc", "recap", "--campaign", self.campaign_id)
        if recap["data"]["recent_turn_diffs"]:
            self.assertIn("diff_summary", recap["data"]["recent_turn_diffs"][0])
            self.assertNotIn("diff", recap["data"]["recent_turn_diffs"][0])

        recap_full = run_dmctl("ooc", "recap", "--campaign", self.campaign_id, "--full")
        if recap_full["data"]["recent_turn_diffs"]:
            self.assertIn("diff", recap_full["data"]["recent_turn_diffs"][0])

    def test_03_ooc_undo_last_turn(self):
        marker = f"Undo-{uuid.uuid4().hex[:6]}"
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        run_dmctl(
            "item",
            "grant",
            "--campaign",
            self.campaign_id,
            payload={
                "owner_type": "pc",
                "owner_id": "pc_hero",
                "item_name": marker,
                "quantity": 1,
            },
        )

        undo = run_dmctl("ooc", "undo_last_turn", "--campaign", self.campaign_id)
        self.assertEqual(undo["command"], "ooc undo_last_turn")
        self.assertEqual(undo["data"]["turn"]["status"], "rolled_back")

        state = run_dmctl("state", "get", "--campaign", self.campaign_id, "--include-hidden", "--full")
        names = {row["item_name"] for row in state["data"]["inventory"]}
        self.assertNotIn(marker, names)

    def test_04_help_returns_json(self):
        result = subprocess.run([str(DMCTL), "--help"], capture_output=True, text=True, cwd=str(ROOT), check=False)
        body = json.loads(result.stdout.strip())
        self.assertTrue(body["ok"])
        self.assertEqual(body["command"], "help")
        self.assertIn("groups", body["data"])
        self.assertGreater(len(body["data"]["groups"]), 0)

        campaign_help = run_dmctl("campaign", "--help")
        self.assertEqual(campaign_help["command"], "help")
        self.assertEqual(campaign_help["data"]["requested_group"], "campaign")
        self.assertIn("create", campaign_help["data"]["requested_actions"])

        prefixed_help = subprocess.run(
            [str(DMCTL), "--campaign", "demo", "campaign", "--help"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            check=False,
        )
        prefixed_body = json.loads(prefixed_help.stdout.strip())
        self.assertTrue(prefixed_body["ok"])
        self.assertEqual(prefixed_body["data"]["requested_group"], "campaign")

        ooc_help = run_dmctl("ooc", "--help")
        self.assertIn("refresh", ooc_help["data"]["requested_actions"])

    def test_05_ooc_undo_last_committed_turn(self):
        marker = f"CommittedUndo-{uuid.uuid4().hex[:6]}"
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        run_dmctl(
            "item",
            "grant",
            "--campaign",
            self.campaign_id,
            payload={
                "owner_type": "pc",
                "owner_id": "pc_hero",
                "item_name": marker,
                "quantity": 1,
            },
        )
        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "Add marker for committed undo")

        pre_undo = run_dmctl("state", "get", "--campaign", self.campaign_id, "--full")
        names_before = {row["item_name"] for row in pre_undo["data"]["inventory"]}
        self.assertIn(marker, names_before)

        undo = run_dmctl("ooc", "undo_last_turn", "--campaign", self.campaign_id)
        self.assertEqual(undo["command"], "ooc undo_last_turn")
        self.assertEqual(undo["data"]["turn"]["status"], "rolled_back")
        self.assertEqual(undo["data"]["turn"]["mode"], "committed")
        self.assertEqual(undo["data"]["turn"]["reason"], "ooc undo_last_turn")

        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        run_dmctl(
            "item",
            "grant",
            "--campaign",
            self.campaign_id,
            payload={
                "owner_type": "pc",
                "owner_id": "pc_hero",
                "item_name": f"{marker}-2",
                "quantity": 1,
            },
        )
        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "Add marker for reason passthrough")
        custom_reason = "manual custom undo reason"
        undo_with_reason = run_dmctl(
            "ooc",
            "undo_last_turn",
            "--campaign",
            self.campaign_id,
            "--reason",
            custom_reason,
        )
        self.assertEqual(undo_with_reason["data"]["turn"]["reason"], custom_reason)

        post_undo = run_dmctl("state", "get", "--campaign", self.campaign_id, "--full")
        names_after = {row["item_name"] for row in post_undo["data"]["inventory"]}
        self.assertNotIn(marker, names_after)
        self.assertNotIn(f"{marker}-2", names_after)

        validate = run_dmctl("validate", "--campaign", self.campaign_id)
        self.assertTrue(validate["ok"])

    def test_06_dashboard_and_recap_use_latest_turn_order(self):
        for idx in range(2):
            run_dmctl("turn", "begin", "--campaign", self.campaign_id)
            run_dmctl(
                "world",
                "pulse",
                "--campaign",
                self.campaign_id,
                payload={"hours": 0, "add_hooks": [f"hook_{idx}"]},
            )
            run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", f"Ordering turn {idx}")

        db_path = CAMPAIGNS_ROOT / self.campaign_id / "campaign.db"
        conn = sqlite3.connect(db_path)
        latest_turn_number = conn.execute(
            "SELECT MAX(turn_number) FROM turns WHERE status = 'committed'"
        ).fetchone()[0]
        conn.close()

        dashboard = run_dmctl("ooc", "dashboard", "--campaign", self.campaign_id)
        self.assertEqual(dashboard["data"]["latest_turn_diff"]["turn_number"], latest_turn_number)

        recap = run_dmctl("recap", "generate", "--campaign", self.campaign_id, payload={"limit": 3})
        turn_numbers = [row["turn_number"] for row in recap["data"]["recent_turn_diffs"]]
        self.assertGreaterEqual(len(turn_numbers), 1)
        self.assertEqual(turn_numbers[0], latest_turn_number)
        self.assertEqual(turn_numbers, sorted(turn_numbers, reverse=True))

    def test_07_ooc_refresh_contract_and_modes(self):
        for idx in range(2):
            run_dmctl("turn", "begin", "--campaign", self.campaign_id)
            run_dmctl(
                "world",
                "pulse",
                "--campaign",
                self.campaign_id,
                payload={"hours": 0, "add_hooks": [f"refresh_contract_hook_{idx}"]},
            )
            run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", f"Refresh contract turn {idx}")

        refresh = run_dmctl("ooc", "refresh", "--campaign", self.campaign_id)
        self.assertEqual(refresh["command"], "ooc refresh")
        for key in ("campaign", "trigger", "mode_requested", "mode_used", "continuity_summary", "memory_packet", "warnings"):
            self.assertIn(key, refresh["data"])
        self.assertEqual(refresh["data"]["trigger"], "manual")
        self.assertEqual(refresh["data"]["mode_requested"], "auto")
        self.assertEqual(refresh["data"]["mode_used"], "compact")
        self.assertIn("ui", refresh["data"])
        self.assertEqual(refresh["data"]["ui"]["template_id"], "ooc_panel")

        packet = refresh["data"]["memory_packet"]
        self.assertIn("world_state", packet)
        self.assertIn("player_status", packet)
        self.assertIn("recent_turn_diffs", packet)
        self.assertIn("state_slices", packet)
        if packet["recent_turn_diffs"]:
            self.assertIn("diff_summary", packet["recent_turn_diffs"][0])
            self.assertNotIn("diff", packet["recent_turn_diffs"][0])

        refresh_full = run_dmctl(
            "ooc",
            "refresh",
            "--campaign",
            self.campaign_id,
            payload={"mode": "full", "turn_limit": 3},
        )
        self.assertEqual(refresh_full["data"]["mode_requested"], "full")
        self.assertEqual(refresh_full["data"]["mode_used"], "full")
        full_packet = refresh_full["data"]["memory_packet"]
        self.assertIn("state_snapshot", full_packet)
        if full_packet["recent_turn_diffs"]:
            self.assertIn("diff", full_packet["recent_turn_diffs"][0])

    def test_08_ooc_refresh_auto_escalates_when_critical_context_missing(self):
        refresh = run_dmctl(
            "ooc",
            "refresh",
            "--campaign",
            self.campaign_id,
            payload={"mode": "auto", "state_paths": "world_state"},
        )
        self.assertEqual(refresh["data"]["mode_requested"], "auto")
        self.assertEqual(refresh["data"]["mode_used"], "full")
        self.assertIn("refresh_auto_escalated_to_full", refresh["data"]["warnings"])
        packet = refresh["data"]["memory_packet"]
        self.assertIn("critical_missing_paths", packet)
        self.assertIn("state_snapshot", packet)

    def test_09_refresh_recent_turn_diffs_use_latest_turn_order(self):
        for idx in range(2):
            run_dmctl("turn", "begin", "--campaign", self.campaign_id)
            run_dmctl(
                "world",
                "pulse",
                "--campaign",
                self.campaign_id,
                payload={"hours": 0, "add_hooks": [f"refresh_order_hook_{idx}"]},
            )
            run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", f"Refresh order turn {idx}")

        dashboard = run_dmctl("ooc", "dashboard", "--campaign", self.campaign_id)
        latest_turn_number = dashboard["data"]["latest_turn_diff"]["turn_number"]

        recap = run_dmctl("recap", "generate", "--campaign", self.campaign_id, payload={"limit": 3})
        recap_turn_numbers = [row["turn_number"] for row in recap["data"]["recent_turn_diffs"]]

        refresh = run_dmctl(
            "ooc",
            "refresh",
            "--campaign",
            self.campaign_id,
            payload={"mode": "compact", "turn_limit": 3},
        )
        refresh_turn_numbers = [row["turn_number"] for row in refresh["data"]["memory_packet"]["recent_turn_diffs"]]
        self.assertGreaterEqual(len(refresh_turn_numbers), 1)
        self.assertEqual(refresh_turn_numbers[0], latest_turn_number)
        self.assertEqual(refresh_turn_numbers, sorted(refresh_turn_numbers, reverse=True))
        self.assertEqual(refresh_turn_numbers, recap_turn_numbers)


if __name__ == "__main__":
    unittest.main(verbosity=2)
