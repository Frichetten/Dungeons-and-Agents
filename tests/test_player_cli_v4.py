import json
import shutil
import subprocess
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DMCTL = ROOT / "tools" / "dmctl"
PCCTL = ROOT / "tools" / "pcctl"
CAMPAIGNS_ROOT = ROOT / ".dm" / "campaigns"


def run_json(cmd, expect_ok=True):
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), check=False)
    try:
        body = json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Command did not return JSON. CMD={cmd} STDOUT={result.stdout} STDERR={result.stderr}") from exc

    if expect_ok and not body.get("ok"):
        raise AssertionError(f"Command failed unexpectedly. CMD={cmd} BODY={body} STDERR={result.stderr}")
    if not expect_ok and body.get("ok"):
        raise AssertionError(f"Command unexpectedly succeeded. CMD={cmd} BODY={body}")
    return body


def run_dmctl(*parts, payload=None, expect_ok=True):
    cmd = [str(DMCTL), *parts]
    if payload is not None:
        cmd.extend(["--payload", json.dumps(payload, separators=(",", ":"))])
    return run_json(cmd, expect_ok=expect_ok)


def run_pcctl(*parts, payload=None, expect_ok=True):
    cmd = [str(PCCTL), *parts]
    if payload is not None:
        cmd.extend(["--payload", json.dumps(payload, separators=(",", ":"))])
    return run_json(cmd, expect_ok=expect_ok)


class TestPlayerCliV4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.campaign_ids = []

    @classmethod
    def tearDownClass(cls):
        for campaign_id in cls.campaign_ids:
            cdir = CAMPAIGNS_ROOT / campaign_id
            if cdir.exists():
                shutil.rmtree(cdir)

    @classmethod
    def create_fixture_campaign(cls, *, second_active=False):
        campaign_id = f"player_v4_{uuid.uuid4().hex[:10]}"
        cls.campaign_ids.append(campaign_id)

        run_dmctl("campaign", "create", "--campaign", campaign_id, "--name", "Player View Fixture")
        run_dmctl("turn", "begin", "--campaign", campaign_id)
        run_dmctl(
            "state",
            "set",
            "--campaign",
            campaign_id,
            payload={
                "locations": [
                    {"id": "loc_start", "name": "Oakcross", "region": "Greenmarch"},
                    {"id": "loc_keep", "name": "Raven Keep", "region": "Greenmarch"},
                    {"id": "loc_ruins", "name": "Ash Ruins", "region": "Greenmarch"},
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
                        "is_active": True,
                    },
                    {
                        "id": "pc_ally",
                        "name": "Bryn Vale",
                        "class": "Fighter",
                        "level": 2,
                        "max_hp": 18,
                        "current_hp": 18,
                        "ac": 14,
                        "location_id": "loc_start",
                        "is_active": bool(second_active),
                    },
                ],
                "world_state": {
                    "world_date": "1 Ches 1492 DR",
                    "world_time": "08:00",
                    "weather": "mist",
                    "region": "Greenmarch",
                    "location_id": "loc_start",
                },
                "hidden_note": "DM private continuity note",
            },
        )
        run_dmctl(
            "npc",
            "create",
            "--campaign",
            campaign_id,
            payload={
                "id": "npc_keeper",
                "name": "Archivist Nera",
                "location_id": "loc_start",
                "max_hp": 11,
                "current_hp": 11,
                "ac": 12,
            },
        )
        run_dmctl(
            "item",
            "grant",
            "--campaign",
            campaign_id,
            payload={"owner_type": "pc", "owner_id": "pc_hero", "item_name": "Torch", "quantity": 2},
        )
        run_dmctl(
            "item",
            "grant",
            "--campaign",
            campaign_id,
            payload={"owner_type": "party", "owner_id": "party", "item_name": "Rope", "quantity": 1},
        )
        run_dmctl(
            "item",
            "grant",
            "--campaign",
            campaign_id,
            payload={"owner_type": "npc", "owner_id": "npc_keeper", "item_name": "Hidden Sigil", "quantity": 1},
        )
        run_dmctl(
            "rumor",
            "add",
            "--campaign",
            campaign_id,
            payload={
                "id": "rumor_public",
                "text": "The keep cellar opens at moonrise.",
                "source": "Tavern",
                "spread_level": 2,
                "decay": 3,
                "truth_status": "true",
                "revealed_to_player": True,
            },
        )
        run_dmctl(
            "rumor",
            "add",
            "--campaign",
            campaign_id,
            payload={
                "id": "rumor_hidden",
                "text": "A hidden vault lies under the chapel.",
                "source": "Unknown",
                "spread_level": 1,
                "decay": 1,
                "truth_status": "false",
                "revealed_to_player": False,
            },
        )
        run_dmctl("turn", "commit", "--campaign", campaign_id, "--summary", "Fixture seeded")
        return campaign_id

    def test_player_rumors_allowlist_and_visibility(self):
        campaign_id = self.create_fixture_campaign()
        rumors = run_dmctl("player", "rumors", "--campaign", campaign_id)
        rows = rumors["data"]["rumors"]
        self.assertEqual([row["id"] for row in rows], ["rumor_public"])
        self.assertEqual(set(rows[0].keys()), {"id", "text", "source", "spread_level", "updated_at"})

    def test_player_items_excludes_npc_inventory(self):
        campaign_id = self.create_fixture_campaign()
        items = run_dmctl("player", "items", "--campaign", campaign_id)
        owners = {(row["owner_type"], row["owner_id"]) for row in items["data"]["items"]}
        self.assertIn(("pc", "pc_hero"), owners)
        self.assertIn(("party", "party"), owners)
        self.assertNotIn(("npc", "npc_keeper"), owners)

    def test_player_sheet_defaults_to_single_active_pc(self):
        campaign_id = self.create_fixture_campaign()
        sheet = run_dmctl("player", "sheet", "--campaign", campaign_id)
        self.assertEqual(sheet["data"]["pc"]["id"], "pc_hero")
        names = {row["item_name"] for row in sheet["data"]["inventory"]}
        self.assertIn("Torch", names)
        self.assertNotIn("Rope", names)

    def test_player_context_ambiguous_requires_pc_id(self):
        campaign_id = self.create_fixture_campaign(second_active=True)
        ambiguous = run_dmctl("player", "sheet", "--campaign", campaign_id, expect_ok=False)
        self.assertEqual(ambiguous["error"], "player_context_ambiguous")

        scoped = run_dmctl("player", "sheet", "--campaign", campaign_id, "--pc-id", "pc_ally")
        self.assertEqual(scoped["data"]["pc"]["id"], "pc_ally")

    def test_player_locations_discovery_tracks_travel(self):
        campaign_id = self.create_fixture_campaign()
        before = run_dmctl("player", "locations", "--campaign", campaign_id)
        before_locations = {row["id"] for row in before["data"]["locations"]}
        self.assertIn("loc_start", before_locations)
        self.assertNotIn("loc_keep", before_locations)
        self.assertNotIn("loc_ruins", before_locations)

        run_dmctl("turn", "begin", "--campaign", campaign_id)
        run_dmctl(
            "travel",
            "resolve",
            "--campaign",
            campaign_id,
            payload={"to_location_id": "loc_keep", "travel_hours": 1},
        )
        run_dmctl("turn", "commit", "--campaign", campaign_id, "--summary", "Travel discovery")

        after = run_dmctl("player", "locations", "--campaign", campaign_id)
        after_locations = {row["id"] for row in after["data"]["locations"]}
        self.assertIn("loc_start", after_locations)
        self.assertIn("loc_keep", after_locations)
        self.assertNotIn("loc_ruins", after_locations)
        current = [row for row in after["data"]["locations"] if row["id"] == "loc_keep"][0]
        self.assertTrue(current["is_current"])

    def test_player_commands_reject_unsafe_dm_flags_and_payload(self):
        campaign_id = self.create_fixture_campaign()
        include_hidden = run_dmctl(
            "player",
            "rumors",
            "--campaign",
            campaign_id,
            "--include-hidden",
            expect_ok=False,
        )
        self.assertEqual(include_hidden["error"], "forbidden_player_option")

        profile = run_dmctl(
            "player",
            "rumors",
            "--campaign",
            campaign_id,
            "--profile",
            "dm_full",
            expect_ok=False,
        )
        self.assertEqual(profile["error"], "forbidden_player_option")

        payload_block = run_dmctl(
            "player",
            "rumors",
            "--campaign",
            campaign_id,
            payload={"include_hidden": True},
            expect_ok=False,
        )
        self.assertEqual(payload_block["error"], "forbidden_player_payload_key")

    def test_pcctl_blocks_dm_only_and_proxies_allowed_commands(self):
        campaign_id = self.create_fixture_campaign()

        blocked = run_pcctl("refresh", "--campaign", campaign_id, expect_ok=False)
        self.assertEqual(blocked["error"], "player_command_blocked")

        unsafe = run_pcctl("rumors", "--campaign", campaign_id, "--include-hidden", expect_ok=False)
        self.assertEqual(unsafe["error"], "forbidden_player_option")

        proxied = run_pcctl("inventory", "--campaign", campaign_id)
        self.assertEqual(proxied["command"], "player items")
        self.assertTrue(proxied["ok"])

    def test_dm_regression_commands_still_support_dm_full(self):
        campaign_id = self.create_fixture_campaign()
        state = run_dmctl("state", "get", "--campaign", campaign_id, "--profile", "dm_full", "--include-hidden", "--full")
        self.assertEqual(state["data"]["profile"], "dm_full")
        self.assertIn("notes_hidden", state["data"])

        refresh = run_dmctl(
            "ooc",
            "refresh",
            "--campaign",
            campaign_id,
            payload={"mode": "full", "include_hidden": True},
        )
        snapshot = refresh["data"]["memory_packet"]["state_snapshot"]
        self.assertEqual(snapshot["profile"], "dm_full")

    def test_help_includes_player_group(self):
        body = run_json([str(DMCTL), "--help"])
        groups = {row["group"]: row["actions"] for row in body["data"]["groups"]}
        self.assertIn("player", groups)
        self.assertIn("sheet", groups["player"])
        self.assertIn("items", groups["player"])

        pcctl_help = run_pcctl("--help")
        self.assertIn("usage", pcctl_help["data"])


if __name__ == "__main__":
    unittest.main()
