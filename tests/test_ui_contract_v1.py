import copy
import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DMCTL = ROOT / "tools" / "dmctl"
CAMPAIGNS_ROOT = ROOT / ".dm" / "campaigns"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "ui_contract_golden.json"

sys.path.insert(0, str(ROOT / "tools"))
from dm.ui_contract import (  # noqa: E402
    TEMPLATE_IDS,
    UI_CONTRACT_VERSION,
    UIContractError,
    parse_choice_input,
    render_markdown,
    resolve_template_id,
    validate_envelope,
)


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


class TestUIContractV1(unittest.TestCase):
    def setUp(self):
        self.campaign_id = f"ui_{uuid.uuid4().hex[:10]}"
        run_dmctl("campaign", "create", "--campaign", self.campaign_id, "--name", "UI Contract V1")
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        run_dmctl(
            "campaign",
            "seed",
            "--campaign",
            self.campaign_id,
            payload={
                "locations": [
                    {"id": "loc_start", "name": "Larkspur", "region": "Greenmarch"},
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
                    "world_date": "3 Ches 1492 DR",
                    "world_time": "09:00",
                    "weather": "clear",
                    "region": "Greenmarch",
                    "location_id": "loc_start",
                },
            },
        )
        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "UI baseline")

    def tearDown(self):
        cdir = CAMPAIGNS_ROOT / self.campaign_id
        if cdir.exists():
            shutil.rmtree(cdir)

    def test_registry_contains_expected_templates(self):
        expected = {
            "scene_turn",
            "dialogue_turn",
            "combat_turn",
            "exploration_turn",
            "skill_check_turn",
            "ooc_panel",
            "system_error",
        }
        self.assertEqual(set(TEMPLATE_IDS), expected)

    def test_template_resolver_maps_game_state_flags(self):
        self.assertEqual(resolve_template_id({"combat": True}), "combat_turn")
        self.assertEqual(resolve_template_id({"dialogue": True}), "dialogue_turn")
        self.assertEqual(resolve_template_id({"exploration": True}), "exploration_turn")
        self.assertEqual(resolve_template_id({"skill_check": True}), "skill_check_turn")
        self.assertEqual(resolve_template_id({"ooc_action": "dashboard"}), "ooc_panel")
        self.assertEqual(resolve_template_id({"error": "no_open_turn"}), "system_error")
        self.assertEqual(resolve_template_id({}), "scene_turn")

    def test_golden_fixture_contract_and_rendering(self):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        for template_id, payload in fixture.items():
            with self.subTest(template_id=template_id):
                envelope = payload["envelope"]
                self.assertEqual(envelope["template_id"], template_id)
                self.assertEqual(validate_envelope(envelope), [])
                self.assertEqual(render_markdown(envelope), payload["rendered"])

    def test_validator_rejects_contract_breaks(self):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        base = fixture["scene_turn"]["envelope"]

        missing_section = copy.deepcopy(base)
        missing_section["sections"] = missing_section["sections"][:-1]
        self.assertTrue(any("sections must contain exactly" in msg for msg in validate_envelope(missing_section)))

        wrong_order = copy.deepcopy(base)
        wrong_order["sections"][0], wrong_order["sections"][1] = wrong_order["sections"][1], wrong_order["sections"][0]
        self.assertTrue(any("sections[0].id must be" in msg for msg in validate_envelope(wrong_order)))

        unexpected_choices = copy.deepcopy(base)
        unexpected_choices["choices"] = [{"id": "1", "label": "Fallback", "intent": "Action", "risk": "Low"}]
        self.assertTrue(any("choices must be empty for actionable template" in msg for msg in validate_envelope(unexpected_choices)))

        nonempty_freeform_hint = copy.deepcopy(base)
        nonempty_freeform_hint["freeform_hint"] = "Or describe another action."
        self.assertTrue(
            any(
                "freeform_hint must be empty for actionable template" in msg
                for msg in validate_envelope(nonempty_freeform_hint)
            )
        )

        missing_prompt = copy.deepcopy(base)
        missing_prompt["prompt"] = "Choose."
        self.assertTrue(any("prompt must exactly match" in msg for msg in validate_envelope(missing_prompt)))

    def test_choice_parser_supports_numeric_label_and_freeform(self):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        envelope = fixture["scene_turn"]["envelope"]

        numeric = parse_choice_input("1", envelope)
        self.assertEqual(numeric["kind"], "freeform")
        self.assertEqual(numeric["text"], "1")

        label = parse_choice_input("Set up an advantage", envelope)
        self.assertEqual(label["kind"], "freeform")
        self.assertEqual(label["text"], "Set up an advantage")

        custom_choices = [
            {"id": "1", "label": "Advance", "intent": "Action", "risk": "Low"},
            {"id": "2", "label": "Hold", "intent": "Action", "risk": "Low"},
        ]
        numeric_preset = parse_choice_input("2", custom_choices)
        self.assertEqual(numeric_preset["kind"], "preset")
        self.assertEqual(numeric_preset["choice_id"], "2")

        label_preset = parse_choice_input("Advance", custom_choices)
        self.assertEqual(label_preset["kind"], "preset")
        self.assertEqual(label_preset["choice_id"], "1")

        freeform = parse_choice_input("Jump to the broken parapet", envelope)
        self.assertEqual(freeform["kind"], "freeform")
        self.assertEqual(freeform["text"], "Jump to the broken parapet")

        with self.assertRaises(UIContractError):
            parse_choice_input("", envelope)

    def test_ooc_responses_include_ui_contract(self):
        dashboard = run_dmctl("ooc", "dashboard", "--campaign", self.campaign_id)
        self.assertIn("ui", dashboard["data"])
        self.assertEqual(dashboard["data"]["ui"]["ui_contract_version"], UI_CONTRACT_VERSION)
        self.assertEqual(dashboard["data"]["ui"]["template_id"], "ooc_panel")
        self.assertIn("ui_markdown", dashboard["data"])

    def test_combat_responses_include_ui_contract(self):
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        run_dmctl(
            "npc",
            "create",
            "--campaign",
            self.campaign_id,
            payload={
                "id": "npc_raider_ui",
                "name": "Road Raider",
                "location_id": "loc_road",
                "max_hp": 16,
                "current_hp": 16,
                "ac": 13,
                "initiative_mod": 1,
            },
        )
        started = run_dmctl(
            "combat",
            "start",
            "--campaign",
            self.campaign_id,
            payload={
                "name": "Road Ambush",
                "location_id": "loc_road",
                "participants": [{"type": "pc", "id": "pc_hero"}, {"type": "npc", "id": "npc_raider_ui"}],
            },
        )
        self.assertEqual(started["data"]["ui"]["template_id"], "combat_turn")
        self.assertEqual(started["data"]["ui"]["ui_contract_version"], UI_CONTRACT_VERSION)

        encounter_id = started["data"]["encounter_id"]
        combatants = started["data"]["combatants"]
        current_actor = combatants[0]
        target = combatants[1] if len(combatants) > 1 else combatants[0]
        acted = run_dmctl(
            "combat",
            "act",
            "--campaign",
            self.campaign_id,
            payload={
                "encounter_id": encounter_id,
                "combatant_id": current_actor["id"],
                "action": "Shortsword strike",
                "target_id": target["id"],
                "damage": 3,
                "end_turn": True,
            },
        )
        self.assertEqual(acted["data"]["ui"]["template_id"], "combat_turn")
        self.assertEqual(acted["data"]["ui"]["ui_contract_version"], UI_CONTRACT_VERSION)

    def test_failure_responses_include_system_error_template(self):
        failed = run_dmctl(
            "state",
            "set",
            "--campaign",
            self.campaign_id,
            payload={"public_note": "Should fail without open turn"},
            expect_ok=False,
        )
        self.assertIn("ui", failed)
        self.assertEqual(failed["ui"]["template_id"], "system_error")
        self.assertEqual(failed["ui"]["ui_contract_version"], UI_CONTRACT_VERSION)
        self.assertIn("ui_markdown", failed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
