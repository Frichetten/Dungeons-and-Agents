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
        raise AssertionError(f"Non-JSON response: cmd={cmd} stdout={result.stdout} stderr={result.stderr}") from exc
    if expect_ok and not body.get("ok"):
        raise AssertionError(f"Unexpected failure: cmd={cmd} body={body} stderr={result.stderr}")
    if not expect_ok and body.get("ok"):
        raise AssertionError(f"Unexpected success: cmd={cmd} body={body}")
    return body


class TestRollPolicyV1(unittest.TestCase):
    def setUp(self):
        self.campaign_id = f"rollpol_{uuid.uuid4().hex[:10]}"
        run_dmctl("campaign", "create", "--campaign", self.campaign_id, "--name", "Roll Policy V1")
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        run_dmctl(
            "campaign",
            "seed",
            "--campaign",
            self.campaign_id,
            payload={
                "locations": [{"id": "loc_start", "name": "Larkspur", "region": "Greenmarch"}],
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
                "npcs": [{"name": "N1"}, {"name": "N2"}, {"name": "N3"}],
                "world_state": {"world_date": "2 Ches 1492 DR", "world_time": "10:00", "location_id": "loc_start"},
            },
        )
        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "Roll policy baseline")

    def tearDown(self):
        cdir = CAMPAIGNS_ROOT / self.campaign_id
        if cdir.exists():
            shutil.rmtree(cdir)

    def _begin_turn(self):
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)

    def test_00_adjudicate_trivial_wait_defaults_no_roll(self):
        body = run_dmctl(
            "dice",
            "adjudicate",
            "--campaign",
            self.campaign_id,
            payload={
                "intent": "Successfully waiting on the street",
                "scene_type": "exploration",
                "stakes": "low",
                "uncertainty_source": "none",
                "opposition": False,
                "retryable_without_cost": True,
                "approach_changed": False,
                "immediate_player_stakes": True,
                "combat_context": False,
                "proposed_roll": "1d20+3",
            },
        )
        self.assertEqual(body["data"]["decision"], "no_roll")
        self.assertTrue(body["data"]["strict_violation"])

    def test_01_adjudicate_world_rng_prefers_deterministic_update(self):
        body = run_dmctl(
            "dice",
            "adjudicate",
            "--campaign",
            self.campaign_id,
            payload={
                "intent": "Determine ambient weather shift",
                "scene_type": "travel",
                "stakes": "low",
                "uncertainty_source": "weather",
                "immediate_player_stakes": False,
            },
        )
        self.assertEqual(body["data"]["decision"], "deterministic_world_update")

    def test_02_adjudicate_contested_high_stakes_requires_roll(self):
        body = run_dmctl(
            "dice",
            "adjudicate",
            "--campaign",
            self.campaign_id,
            payload={
                "intent": "Convince the guard to release a prisoner",
                "scene_type": "dialogue",
                "stakes": "high",
                "uncertainty_source": "social_resistance",
                "opposition": True,
                "immediate_player_stakes": True,
            },
        )
        self.assertEqual(body["data"]["decision"], "roll_required")
        self.assertFalse(body["data"]["strict_violation"])

    def test_03_adjudicate_passive_observation_prefers_passive(self):
        body = run_dmctl(
            "dice",
            "adjudicate",
            "--campaign",
            self.campaign_id,
            payload={
                "intent": "Passive observation for hidden tells",
                "scene_type": "dialogue",
                "stakes": "medium",
                "uncertainty_source": "hidden_information",
                "immediate_player_stakes": True,
            },
        )
        self.assertEqual(body["data"]["decision"], "use_passive")

    def test_04_warn_mode_allows_violation_but_flags_warning(self):
        self._begin_turn()
        adjudication = run_dmctl(
            "dice",
            "adjudicate",
            "--campaign",
            self.campaign_id,
            payload={
                "intent": "Wait quietly on the street for signs of movement",
                "scene_type": "exploration",
                "stakes": "low",
                "uncertainty_source": "none",
                "retryable_without_cost": True,
                "immediate_player_stakes": True,
            },
        )["data"]
        roll = run_dmctl(
            "dice",
            "roll",
            "--campaign",
            self.campaign_id,
            payload={
                "formula": "1d20+3",
                "context": "wait_on_street_interval",
                "adjudication": adjudication,
                "policy_mode": "warn",
            },
        )
        self.assertIn("roll_policy_violation", roll["warnings"])
        self.assertEqual(roll["data"]["policy_decision"], "no_roll")

    def test_05_strict_mode_blocks_policy_violation_without_override(self):
        self._begin_turn()
        adjudication = run_dmctl(
            "dice",
            "adjudicate",
            "--campaign",
            self.campaign_id,
            payload={
                "intent": "Hold position and keep waiting",
                "scene_type": "exploration",
                "stakes": "low",
                "uncertainty_source": "none",
                "retryable_without_cost": True,
                "immediate_player_stakes": True,
            },
        )["data"]
        blocked = run_dmctl(
            "dice",
            "roll",
            "--campaign",
            self.campaign_id,
            payload={
                "formula": "1d20+2",
                "context": "hold_and_wait",
                "adjudication": adjudication,
                "policy_mode": "strict",
            },
            expect_ok=False,
        )
        self.assertEqual(blocked["error"], "roll_policy_violation")

        allowed = run_dmctl(
            "dice",
            "roll",
            "--campaign",
            self.campaign_id,
            payload={
                "formula": "1d20+2",
                "context": "hold_and_wait",
                "adjudication": adjudication,
                "policy_mode": "strict",
                "override_reason": "Exceptional narrative pacing override for playtest",
            },
        )
        self.assertIn("roll_policy_override_applied", allowed["warnings"])

    def test_06_combat_context_rolls_not_blocked_in_strict_mode(self):
        self._begin_turn()
        roll = run_dmctl(
            "dice",
            "roll",
            "--campaign",
            self.campaign_id,
            payload={
                "formula": "1d20+5",
                "context": "combat_resolve_attack:enc_1:a->b",
                "policy_mode": "strict",
            },
        )
        self.assertEqual(roll["data"]["policy_decision"], "roll_required")
        self.assertEqual(roll["warnings"], [])

    def test_07_roll_log_schema_and_dashboard_metrics_present(self):
        self._begin_turn()
        run_dmctl(
            "dice",
            "roll",
            "--campaign",
            self.campaign_id,
            payload={
                "formula": "1d20+1",
                "context": "missing_adjudication_probe",
                "policy_mode": "warn",
            },
        )
        dashboard = run_dmctl("ooc", "dashboard", "--campaign", self.campaign_id)
        self.assertIn("roll_policy", dashboard["data"])
        self.assertGreaterEqual(dashboard["data"]["roll_policy"]["flagged_rolls"], 1)

        db_path = CAMPAIGNS_ROOT / self.campaign_id / "campaign.db"
        conn = sqlite3.connect(db_path)
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(roll_log)").fetchall()
        }
        conn.close()
        for column in (
            "adjudication_id",
            "policy_decision",
            "policy_mode",
            "strict_violation",
            "override_reason",
            "reason_codes_json",
        ):
            self.assertIn(column, columns)

    def test_08_validate_includes_roll_policy_payload(self):
        self._begin_turn()
        run_dmctl(
            "dice",
            "roll",
            "--campaign",
            self.campaign_id,
            payload={"formula": "1d20+2", "context": "validate_roll_policy_probe", "policy_mode": "warn"},
        )
        validate = run_dmctl("validate", "--campaign", self.campaign_id)
        result = validate["data"]["results"][0]
        self.assertIn("roll_policy", result)
        self.assertGreaterEqual(result["roll_policy"]["total_rolls"], 1)

    def test_09_regression_wait_timing_patterns_classify_as_non_roll(self):
        samples = [
            "Veilshadow waiting watch for incoming activity",
            "Hold position one block away while awaiting signal",
            "Keep watch and wait for the runner",
        ]
        for sample in samples:
            body = run_dmctl(
                "dice",
                "adjudicate",
                "--campaign",
                self.campaign_id,
                payload={
                    "intent": sample,
                    "scene_type": "exploration",
                    "stakes": "low",
                    "uncertainty_source": "background_timing",
                    "retryable_without_cost": True,
                    "immediate_player_stakes": False,
                },
            )
            self.assertIn(body["data"]["decision"], {"no_roll", "deterministic_world_update", "use_passive"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
